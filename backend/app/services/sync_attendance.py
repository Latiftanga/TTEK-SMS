"""
Offline sync for Attendance — mirrors services/sync.py's Score-sync shape
(idempotency, clock-skew clamp, validate-before-conflict-check, conflict
detection, resolve_conflict apply) exactly, but validates through
Attendance's OWN scope/term-lock helpers (core/teacher_scope.py::
check_class_in_attendance_scope/enforce_current_term_for_attendance), not
Score's — the two entities have genuinely different rules.

CONFLICT DETECTION
------------------
If AttendanceRecord.recorded_at > item.offline_session_started_at → the
server received a newer write after the offline session began → conflict.
(Score's equivalent field is submitted_at; AttendanceRecord's is recorded_at.)

An offline-synced ABSENT mark fires the exact same guardian notifications
(absence SMS/email, consecutive-absence trigger, chronic-absenteeism risk
check) as the online mark_attendance() path — a family shouldn't be
notified only when their child's teacher happened to have connectivity.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override
from app.core.teacher_scope import enforce_current_term_for_attendance
from app.models.attendance import AttendanceAuditLog, AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.documents import OfflineSyncConflict, OutboxProcessedItem
from app.models.school import School
from app.models.students import Student
from app.schemas.sync import OutboxAttendanceData, OutboxItem, OutboxItemResult
from app.services import attendance_risk as risk_svc
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc
from app.services.academic_class import get_active_class
from app.services.attendance_shared import _MARKABLE_TYPES, check_class_in_attendance_scope
from app.services.sync_shared import clamp_session_start, find_processed_item


async def _assert_attendance_target_in_school(
    data: OutboxAttendanceData, school_id: uuid.UUID, db: AsyncSession
) -> SchoolCalendar:
    cal = await db.get(SchoolCalendar, data.school_calendar_id)
    if not cal or cal.school_id != school_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "school_calendar_id not found for this school.")
    student = await db.get(Student, data.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id not found for this school.")
    return cal


async def _validate_attendance_write(
    data: OutboxAttendanceData,
    cal: SchoolCalendar,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    override_reason: str | None,
    db: AsyncSession,
) -> str | None:
    """Every check services/attendance.py::mark_attendance() enforces for an
    online write, applied identically here. Returns the resolved override
    reason (None if the term isn't locked), for AttendanceAuditLog.reason."""
    await get_active_class(data.class_id, school_id, db)
    await check_class_in_attendance_scope(data.class_id, cal.academic_term_id, user_id, db)
    await enforce_current_term_for_attendance(user_id, cal.academic_term_id, db)

    resolved_reason: str | None = None
    if cal.academic_term_id is not None:
        resolved_reason = await check_term_lock_override(cal.academic_term_id, override_reason, user_id, db)

    if cal.day_type not in _MARKABLE_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cannot mark attendance on a {cal.day_type.value} day.",
        )
    return resolved_reason


async def _write_attendance(
    data: OutboxAttendanceData,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    resolved_reason: str | None = None,
) -> tuple[AttendanceRecord, bool]:
    """Pure write, no validation. Returns (record, is_new_absent) — True only
    for a freshly-inserted ABSENT record, mirroring mark_attendance()'s
    new_absent_ids semantics so the same notifications fire as online."""
    now = datetime.now(timezone.utc)
    existing = await db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == data.student_id,
            AttendanceRecord.school_calendar_id == data.school_calendar_id,
            AttendanceRecord.period_id.is_(None),
        )
    )
    is_new_absent = False
    if existing:
        existing.status = data.status
        existing.notes = data.notes
        existing.recorded_by_id = user_id
        existing.recorded_at = now
        rec = existing
    else:
        rec = AttendanceRecord(
            school_id=school_id, student_id=data.student_id,
            school_calendar_id=data.school_calendar_id, class_id=data.class_id,
            status=data.status, notes=data.notes,
            recorded_by_id=user_id, recorded_at=now,
        )
        db.add(rec)
        await db.flush()
        is_new_absent = data.status == AttendanceStatus.ABSENT

    if resolved_reason:
        db.add(AttendanceAuditLog(
            school_id=school_id, attendance_record_id=rec.id, student_id=data.student_id,
            class_id=data.class_id, status=data.status, changed_by_id=user_id,
            reason=resolved_reason, changed_at=now,
        ))
    await db.flush()
    return rec, is_new_absent


async def _fire_side_effects(
    rec: AttendanceRecord, data: OutboxAttendanceData, cal: SchoolCalendar,
    is_new_absent: bool, school_id: uuid.UUID, db: AsyncSession,
) -> None:
    if is_new_absent:
        school = await db.get(School, school_id)
        school_short = (school.short_name or school.name) if school else ""
        absence_date = cal.date.isoformat()
        await sms_svc.notify_attendance_absent(
            student_id=data.student_id, school_id=school_id, school_short=school_short,
            absence_date=absence_date, entity_id=rec.id, db=db,
        )
        await email_svc.notify_attendance_absent_email(
            student_id=data.student_id, school_id=school_id, school_short=school_short,
            absence_date=absence_date, entity_id=rec.id, db=db,
        )
        if await risk_svc.check_consecutive_absences(data.student_id, data.school_calendar_id, school_id, db):
            await sms_svc.notify_consecutive_absence(
                student_id=data.student_id, school_id=school_id,
                school_short=school_short, entity_id=rec.id, db=db,
            )
            await email_svc.notify_consecutive_absence_email(
                student_id=data.student_id, school_id=school_id,
                school_short=school_short, entity_id=rec.id, db=db,
            )

    if cal.academic_term_id is not None:
        await risk_svc.check_and_notify_risk([data.student_id], cal.academic_term_id, cal.date, school_id, db)


async def _apply_attendance(
    data: OutboxAttendanceData,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    override_reason: str | None = None,
) -> None:
    """Validate-then-write — used by sync.py::resolve_conflict(), which
    (unlike _sync_attendance) doesn't already have a validated calendar day
    in hand."""
    cal = await _assert_attendance_target_in_school(data, school_id, db)
    resolved_reason = await _validate_attendance_write(data, cal, school_id, user_id, override_reason, db)
    rec, is_new_absent = await _write_attendance(data, school_id, user_id, db, resolved_reason)
    await _fire_side_effects(rec, data, cal, is_new_absent, school_id, db)


async def _sync_attendance(
    item: OutboxItem,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> OutboxItemResult:
    processed = await find_processed_item(school_id, user_id, item.client_op_id, db)
    if processed:
        return OutboxItemResult(
            outbox_id=item.outbox_id, status=processed.status, conflict_id=processed.conflict_id,
        )

    data = item.data
    assert isinstance(data, OutboxAttendanceData)
    offline_ts = clamp_session_start(item.offline_session_started_at)

    # Validated once, up front — before the conflict/apply branch below —
    # so an out-of-scope caller is rejected outright rather than being able
    # to provoke an OfflineSyncConflict row that would leak another class's
    # existing attendance record into server_data.
    cal = await _assert_attendance_target_in_school(data, school_id, db)
    resolved_reason = await _validate_attendance_write(data, cal, school_id, user_id, item.override_reason, db)

    existing = await db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == data.student_id,
            AttendanceRecord.school_calendar_id == data.school_calendar_id,
            AttendanceRecord.period_id.is_(None),
        )
    )

    now = datetime.now(timezone.utc)

    if existing and existing.recorded_at and existing.recorded_at > offline_ts:
        conflict = OfflineSyncConflict(
            school_id=school_id,
            user_id=user_id,
            outbox_id=item.outbox_id,
            entity_type="attendance",
            client_data={
                "student_id": str(data.student_id),
                "school_calendar_id": str(data.school_calendar_id),
                "class_id": str(data.class_id),
                "status": data.status.value,
                "notes": data.notes,
            },
            server_data={
                "status": existing.status.value,
                "recorded_at": existing.recorded_at.isoformat(),
                "notes": existing.notes,
            },
            conflict_type="CONCURRENT_EDIT",
            created_at=now,
        )
        db.add(conflict)
        await db.flush()
        db.add(OutboxProcessedItem(
            school_id=school_id, user_id=user_id, client_op_id=item.client_op_id,
            status="conflict", conflict_id=conflict.id, processed_at=now,
        ))
        await db.flush()
        return OutboxItemResult(outbox_id=item.outbox_id, status="conflict", conflict_id=conflict.id)

    rec, is_new_absent = await _write_attendance(data, school_id, user_id, db, resolved_reason)
    await _fire_side_effects(rec, data, cal, is_new_absent, school_id, db)
    db.add(OutboxProcessedItem(
        school_id=school_id, user_id=user_id, client_op_id=item.client_op_id,
        status="applied", conflict_id=None, processed_at=now,
    ))
    await db.flush()
    return OutboxItemResult(outbox_id=item.outbox_id, status="applied")
