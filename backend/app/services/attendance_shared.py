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
from app.models.academic import SubjectTeacher
from app.models.attendance import AttendanceRecord, DayType
from app.schemas.attendance import AttendanceRecordRead

_MARKABLE_TYPES = {DayType.SCHOOL_DAY, DayType.EXAM_DAY, DayType.HALF_DAY}


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
