"""
Attendance recording.

MARKING RULES
-------------
- school_calendar.day_type must be SCHOOL_DAY, EXAM_DAY, or HALF_DAY.
- Re-submitting attendance for the same student+calendar+period updates the record.
- period_id is NULL for daily (whole-day) attendance; non-NULL for period-level.
- class_id and every student_id must belong to the calling school (mirrors the
  ownership checks elsewhere, e.g. create_assessment's ClassSubject check).
- If the calendar day's term has AcademicTerm.results_locked set, marking
  requires assessments.approve_scores + a non-blank override_reason — same
  mechanism as scoring.py/behaviour.py/student_subject_registration.py.
- class_id must be one the caller is ClassTeacher of this year, unless they
  hold attendance.approve (services/attendance_shared.py, core/teacher_scope.py).

Read-only summaries (get_summary/get_today_status/get_class_summaries) and
the "my classes" picker live in services/attendance_summary.py.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override
from app.core.teacher_scope import enforce_current_term_for_attendance
from app.models.academic import Class
from app.models.attendance import AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.school import School
from app.models.students import Student
from app.schemas.attendance import AttendanceMarkRequest, AttendanceRecordRead
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc
from app.services.attendance_shared import _MARKABLE_TYPES, _to_read, check_class_in_attendance_scope


async def mark_attendance(
    req: AttendanceMarkRequest,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[AttendanceRecordRead]:
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.id == req.school_calendar_id,
            SchoolCalendar.school_id == school_id,
        )
    )
    if not cal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar day not found.")

    cls = await db.get(Class, req.class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")

    await check_class_in_attendance_scope(req.class_id, cal.academic_term_id, user_id, db)
    await enforce_current_term_for_attendance(user_id, cal.academic_term_id, db)

    student_ids = {m.student_id for m in req.records}
    valid_ids = set(await db.scalars(
        select(Student.id).where(Student.id.in_(student_ids), Student.school_id == school_id)
    ))
    invalid_ids = student_ids - valid_ids
    if invalid_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Student(s) not found in this school: {', '.join(str(i) for i in invalid_ids)}",
        )

    if cal.academic_term_id is not None:
        await check_term_lock_override(cal.academic_term_id, req.override_reason, user_id, db)

    if cal.day_type not in _MARKABLE_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cannot mark attendance on a {cal.day_type.value} day.",
        )

    now = datetime.now(timezone.utc)
    saved: list[AttendanceRecord] = []
    new_absent_ids: set = set()   # student_ids that are newly marked ABSENT (not re-marks)

    for mark in req.records:
        existing = await db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == mark.student_id,
                AttendanceRecord.school_calendar_id == req.school_calendar_id,
                AttendanceRecord.period_id.is_(None),
            )
        )
        if existing:
            existing.status = mark.status
            existing.notes = mark.notes
            existing.recorded_by_id = user_id
            existing.recorded_at = now
            saved.append(existing)
        else:
            rec = AttendanceRecord(
                school_id=school_id,
                student_id=mark.student_id,
                school_calendar_id=req.school_calendar_id,
                class_id=req.class_id,
                status=mark.status,
                notes=mark.notes,
                recorded_by_id=user_id,
                recorded_at=now,
            )
            db.add(rec)
            saved.append(rec)
            if mark.status == AttendanceStatus.ABSENT:
                new_absent_ids.add(mark.student_id)

    await db.flush()

    # Fire absence alerts only for NEW ABSENT marks — never on re-marks
    if new_absent_ids:
        school = await db.get(School, school_id)
        school_short = (school.short_name or school.name) if school else ""
        absence_date = cal.date.isoformat()
        for rec, mark in zip(saved, req.records):
            if mark.student_id in new_absent_ids:
                await sms_svc.notify_attendance_absent(
                    student_id=mark.student_id,
                    school_id=school_id,
                    school_short=school_short,
                    absence_date=absence_date,
                    entity_id=rec.id,
                    db=db,
                )
                await email_svc.notify_attendance_absent_email(
                    student_id=mark.student_id,
                    school_id=school_id,
                    school_short=school_short,
                    absence_date=absence_date,
                    entity_id=rec.id,
                    db=db,
                )

    return [_to_read(r) for r in saved]


async def list_attendance(
    school_calendar_id: uuid.UUID,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[AttendanceRecordRead]:
    cal = await db.get(SchoolCalendar, school_calendar_id)
    if cal and cal.school_id == school_id:
        await check_class_in_attendance_scope(class_id, cal.academic_term_id, user_id, db)
    rows = await db.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.school_calendar_id == school_calendar_id,
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.period_id.is_(None),
        ).order_by(AttendanceRecord.recorded_at)
    )
    return [_to_read(r) for r in rows]
