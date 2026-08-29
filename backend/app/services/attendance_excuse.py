"""
Guardian/student-submitted absence excuse requests.

REVIEW RULE
-----------
On APPROVED, every markable SchoolCalendar day in [start_date, end_date] is
marked EXCUSED for the student. This deliberately does NOT enforce
enforce_current_term_for_attendance (excusing a recent past absence for a
term that has since stopped being "current" is the normal case, not an
edge case to block) — it DOES still honour check_term_lock_override(), since
a results_locked term is genuinely closed for editing regardless of why.

A day is skipped (not excused, not an error) if the student had no active
class assignment for that day's academic year — there is nothing to excuse
attendance against.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override
from app.core.teacher_scope import resolve_attendance_scope, year_for_term
from app.models.attendance import AttendanceAuditLog, AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.attendance_excuse import AbsenceExcuseRequest, ExcuseStatus
from app.models.school import School
from app.models.students import Student, StudentClassAssignment
from app.schemas.attendance_excuse import ExcuseRequestCreate, ExcuseRequestRead, ExcuseRequestReview
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc
from app.services.academic_year import get_current_year
from app.services.attendance_shared import _MARKABLE_TYPES, check_class_in_attendance_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_read(r: AbsenceExcuseRequest, student_name: str | None = None) -> ExcuseRequestRead:
    data = ExcuseRequestRead.model_validate(r)
    data.student_name = student_name
    return data


async def submit_excuse_request(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID | None,
    requested_by_user_id: uuid.UUID,
    req: ExcuseRequestCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ExcuseRequestRead:
    excuse = AbsenceExcuseRequest(
        school_id=school_id,
        student_id=student_id,
        guardian_id=guardian_id,
        requested_by_user_id=requested_by_user_id,
        start_date=req.start_date,
        end_date=req.end_date,
        reason=req.reason,
        status=ExcuseStatus.PENDING,
    )
    db.add(excuse)
    await db.flush()
    return _to_read(excuse)


async def list_my_excuse_requests(
    student_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> list[ExcuseRequestRead]:
    rows = await db.scalars(
        select(AbsenceExcuseRequest)
        .where(AbsenceExcuseRequest.student_id == student_id, AbsenceExcuseRequest.school_id == school_id)
        .order_by(AbsenceExcuseRequest.created_at.desc())
    )
    return [_to_read(r) for r in rows]


async def list_pending_excuse_requests(
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> list[ExcuseRequestRead]:
    requests = list(await db.scalars(
        select(AbsenceExcuseRequest)
        .where(AbsenceExcuseRequest.school_id == school_id, AbsenceExcuseRequest.status == ExcuseStatus.PENDING)
        .order_by(AbsenceExcuseRequest.created_at)
    ))
    if not requests:
        return []

    # Same "no current year → unrestricted" convention already used by
    # list_my_classes/get_marking_status in this module — not Housing's
    # stricter "no current year → deny" convention, which is specific to
    # Housing's own lack of any other admin-tiering signal (see 12bp).
    year = await get_current_year(school_id, db)
    scope = await resolve_attendance_scope(user_id, year.id, db) if year else None
    if scope is not None:
        student_ids = [r.student_id for r in requests]
        assignment_rows = await db.execute(
            select(StudentClassAssignment.student_id, StudentClassAssignment.class_id).where(
                StudentClassAssignment.student_id.in_(student_ids),
                StudentClassAssignment.academic_year_id == year.id,
                StudentClassAssignment.is_active.is_(True),
            )
        )
        class_by_student = {row.student_id: row.class_id for row in assignment_rows}
        requests = [r for r in requests if class_by_student.get(r.student_id) in scope]
    if not requests:
        return []

    students = {
        s.id: s for s in await db.scalars(
            select(Student).where(Student.id.in_([r.student_id for r in requests]))
        )
    }
    return [
        _to_read(r, f"{s.first_name} {s.last_name}" if (s := students.get(r.student_id)) else None)
        for r in requests
    ]


async def _apply_excuse(
    excuse: AbsenceExcuseRequest, override_reason: str | None, user_id: uuid.UUID,
    school_id: uuid.UUID, db: AsyncSession,
) -> None:
    days = list(await db.scalars(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date >= excuse.start_date,
            SchoolCalendar.date <= excuse.end_date,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
        )
    ))
    if not days:
        return

    # Resolve class + validate scope/term-lock for every day FIRST — a
    # mid-batch failure must not leave some days excused and others not.
    plan: list[tuple[SchoolCalendar, uuid.UUID, str | None]] = []
    year_cache: dict[uuid.UUID, uuid.UUID | None] = {}
    for cal in days:
        if cal.academic_term_id is None:
            continue
        if cal.academic_term_id not in year_cache:
            year_cache[cal.academic_term_id] = await year_for_term(cal.academic_term_id, db)
        year_id = year_cache[cal.academic_term_id]
        if year_id is None:
            continue
        class_id = await db.scalar(
            select(StudentClassAssignment.class_id).where(
                StudentClassAssignment.student_id == excuse.student_id,
                StudentClassAssignment.academic_year_id == year_id,
                StudentClassAssignment.is_active.is_(True),
            )
        )
        if class_id is None:
            continue  # student had no class assignment that year — nothing to excuse
        await check_class_in_attendance_scope(class_id, cal.academic_term_id, user_id, db)
        resolved_reason = await check_term_lock_override(cal.academic_term_id, override_reason, user_id, db)
        plan.append((cal, class_id, resolved_reason))

    now = _utcnow()
    for cal, class_id, resolved_reason in plan:
        existing = await db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == excuse.student_id,
                AttendanceRecord.school_calendar_id == cal.id,
                AttendanceRecord.period_id.is_(None),
            )
        )
        if existing:
            existing.status = AttendanceStatus.EXCUSED
            existing.recorded_by_id = user_id
            existing.recorded_at = now
            rec = existing
        else:
            rec = AttendanceRecord(
                school_id=school_id, student_id=excuse.student_id, school_calendar_id=cal.id,
                class_id=class_id, status=AttendanceStatus.EXCUSED,
                recorded_by_id=user_id, recorded_at=now,
            )
            db.add(rec)
            await db.flush()
        if resolved_reason:
            db.add(AttendanceAuditLog(
                school_id=school_id, attendance_record_id=rec.id, student_id=excuse.student_id,
                class_id=class_id, status=AttendanceStatus.EXCUSED, changed_by_id=user_id,
                reason=resolved_reason, changed_at=now,
            ))
    await db.flush()


async def review_excuse_request(
    request_id: uuid.UUID,
    req: ExcuseRequestReview,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ExcuseRequestRead:
    excuse = await db.scalar(
        select(AbsenceExcuseRequest).where(
            AbsenceExcuseRequest.id == request_id, AbsenceExcuseRequest.school_id == school_id,
        )
    )
    if not excuse:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Excuse request not found.")
    if excuse.status != ExcuseStatus.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This request has already been {excuse.status.value.lower()}.",
        )

    approved = req.status == ExcuseStatus.APPROVED
    if approved:
        await _apply_excuse(excuse, req.override_reason, user_id, school_id, db)

    excuse.status = req.status
    excuse.review_notes = req.review_notes
    excuse.reviewed_by_id = user_id
    excuse.reviewed_at = _utcnow()
    await db.flush()

    school = await db.get(School, school_id)
    school_short = (school.short_name or school.name) if school else ""
    await sms_svc.notify_excuse_decision(
        student_id=excuse.student_id, school_id=school_id, school_short=school_short,
        approved=approved, entity_id=excuse.id, db=db,
    )
    await email_svc.notify_excuse_decision_email(
        student_id=excuse.student_id, school_id=school_id, school_short=school_short,
        approved=approved, entity_id=excuse.id, db=db,
    )
    return _to_read(excuse)
