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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import resolve_attendance_scope, year_for_term
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
