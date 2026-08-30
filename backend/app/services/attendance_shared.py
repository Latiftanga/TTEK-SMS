"""
Shared helpers between services/attendance.py (marking) and
services/attendance_summary.py (reporting) — split out to avoid one file
importing the other's "private" underscore helpers, same pattern as
report_card_scoring.py being a shared leaf module for report_card.py and
report_card_rank.py.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import resolve_attendance_scope, year_for_term
from app.models.academic import SubjectTeacher, TimetableSlot
from app.models.attendance import AttendanceRecord, DayOfWeek, DayType, SchoolCalendar, SchoolPeriod
from app.models.school import School
from app.schemas.attendance import AttendanceRecordRead

_MARKABLE_TYPES = {DayType.SCHOOL_DAY, DayType.EXAM_DAY, DayType.HALF_DAY}
_DAYS_IN_ORDER = list(DayOfWeek)


def _to_read(r: AttendanceRecord) -> AttendanceRecordRead:
    return AttendanceRecordRead.model_validate(r)


def _status_str(val: object) -> str:
    return val.value if hasattr(val, "value") else str(val)


async def check_class_in_attendance_scope(
    class_id: uuid.UUID, academic_term_id: uuid.UUID | None, user_id: uuid.UUID, db: AsyncSession,
) -> None:
    year_id = await year_for_term(academic_term_id, db)
    if year_id is None:
        return
    scope = await resolve_attendance_scope(user_id, year_id, db)
    if scope is not None and class_id not in scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")


async def _staff_member_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    """Duplicated rather than imported — matches the established convention
    in core/teacher_scope.py/student_scope.py/housing_scope.py/
    services/timetable.py, each keeping its own private copy."""
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user or user.is_superadmin:
        return None
    return user.staff_member_id


async def check_period_attendance_scope(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID | None,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Same bypass/ClassTeacher rules as check_class_in_attendance_scope,
    ORing in one more path: the caller is the active SubjectTeacher of this
    exact (class_id, subject_id) this year — the period's own teacher, who
    daily (whole-day) marking's plain ClassTeacher-only scope would
    otherwise shut out of marking their own lesson."""
    year_id = await year_for_term(academic_term_id, db)
    if year_id is None:
        return
    scope = await resolve_attendance_scope(user_id, year_id, db)
    if scope is None or class_id in scope:
        return

    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is not None:
        is_subject_teacher = await db.scalar(
            select(SubjectTeacher.id).where(
                SubjectTeacher.class_id == class_id,
                SubjectTeacher.subject_id == subject_id,
                SubjectTeacher.academic_year_id == year_id,
                SubjectTeacher.staff_member_id == staff_id,
                SubjectTeacher.is_active.is_(True),
            )
        )
        if is_subject_teacher is not None:
            return

    raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")


async def validate_period_marking(
    class_id: uuid.UUID,
    period_id: uuid.UUID,
    cal: SchoolCalendar,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Only called when a mark carries a period_id — the whole-day path
    never reaches this. Confirms the school has opted in, the period is
    real and actually falls on this calendar day's weekday (periods are a
    recurring weekly template, so a mismatch means marking Monday's period
    against a calendar row that's actually a Wednesday), and a subject is
    timetabled for it — then defers the actual who-can-mark-it question to
    check_period_attendance_scope. Shared by the online path
    (services/attendance.py::mark_attendance) and the offline sync path
    (services/sync_attendance.py) so a write can never reach AttendanceRecord
    through one route with weaker rules than the other."""
    school = await db.get(School, school_id)
    if not school or not school.has_period_attendance:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Period-level attendance is not enabled for this school.",
        )

    period = await db.get(SchoolPeriod, period_id)
    if not period or period.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Period not found.")
    if period.day_of_week != _DAYS_IN_ORDER[cal.date.weekday()]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{period.name} is a {period.day_of_week.value} period — this calendar day falls on a different weekday.",
        )

    year_id = await year_for_term(cal.academic_term_id, db)
    slot = None
    if year_id is not None:
        slot = await db.scalar(
            select(TimetableSlot).where(
                TimetableSlot.class_id == class_id,
                TimetableSlot.period_id == period_id,
                TimetableSlot.academic_year_id == year_id,
            )
        )
    if not slot:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No subject is timetabled for this period — nothing to take attendance for.",
        )

    await check_period_attendance_scope(class_id, slot.subject_id, cal.academic_term_id, user_id, db)
