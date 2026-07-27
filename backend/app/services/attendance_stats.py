"""
Shared attendance-rate computation — the one definition of "days present" /
"total school days" used by report_card.py, transcript.py, and (for the
present/total pair specifically) attendance.py's own summary endpoints.

Both counts are scoped to each calendar day's CURRENT day_type, not whatever
it was when attendance was originally marked — override_calendar_day() and
generate_calendar(force=True) can both reclassify a day after the fact, and a
record on a day that's no longer markable must not keep counting.
"""
from __future__ import annotations
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord, DayType, SchoolCalendar

MARKABLE_DAY_TYPES = {DayType.SCHOOL_DAY, DayType.EXAM_DAY, DayType.HALF_DAY}


async def compute_attendance_stats(
    student_id: uuid.UUID,
    term_ids: list[uuid.UUID],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> dict[uuid.UUID, tuple[int, int]]:
    """Returns {term_id: (days_present, total_markable_days)} for every term_id
    that has at least one markable calendar day or one matching attendance
    record — a term with neither simply won't appear in the result."""
    if not term_ids:
        return {}

    markable = [t.value for t in MARKABLE_DAY_TYPES]

    total_rows = await db.execute(
        select(SchoolCalendar.academic_term_id, func.count().label("total"))
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id.in_(term_ids),
            SchoolCalendar.day_type.in_(markable),
        )
        .group_by(SchoolCalendar.academic_term_id)
    )
    stats = {row.academic_term_id: [0, row.total] for row in total_rows}

    present_rows = await db.execute(
        select(
            SchoolCalendar.academic_term_id,
            func.sum(case((AttendanceRecord.status == "PRESENT", 1), else_=0)).label("present"),
        )
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.period_id.is_(None),
            SchoolCalendar.academic_term_id.in_(term_ids),
            SchoolCalendar.day_type.in_(markable),
        )
        .group_by(SchoolCalendar.academic_term_id)
    )
    for row in present_rows:
        stats.setdefault(row.academic_term_id, [0, 0])[0] = row.present or 0

    return {term_id: (present, total) for term_id, (present, total) in stats.items()}
