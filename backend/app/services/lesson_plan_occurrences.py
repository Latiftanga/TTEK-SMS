"""
Resolves "which real scheduled occurrences does this class+subject have in
this week?" — generalizes attendance_periods.py::list_markable_periods()'s
single-date join (SchoolCalendar date -> weekday -> SchoolPeriod ->
TimetableSlot) across every real school day in a date range, instead of one
date at a time.

No new "occurrence" table — deliberately resolved on the fly from the
existing recurring weekly template (TimetableSlot) and the existing real
per-date calendar (SchoolCalendar), per this feature's own scoping decision.
An occurrence's identity is just (school_calendar_id, period_id) — both
already real, stable ids, sufficient to detect drift later without a new
materialized table.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import TimetableSlot
from app.models.attendance import DayOfWeek, SchoolCalendar, SchoolPeriod
from app.services.attendance_shared import _MARKABLE_TYPES

_DAYS_IN_ORDER = list(DayOfWeek)


@dataclass(frozen=True)
class ResolvedOccurrence:
    school_calendar_id: uuid.UUID
    period_id: uuid.UUID
    lesson_date: date
    start_time: object
    end_time: object


async def resolve_week_occurrences(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    week_start: date,
    week_end: date,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[ResolvedOccurrence]:
    cal_days = list(await db.scalars(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date >= week_start,
            SchoolCalendar.date <= week_end,
            SchoolCalendar.day_type.in_(_MARKABLE_TYPES),
        ).order_by(SchoolCalendar.date)
    ))
    if not cal_days:
        return []

    all_periods = list(await db.scalars(
        select(SchoolPeriod).where(SchoolPeriod.school_id == school_id)
    ))
    periods_by_day: dict[DayOfWeek, list[SchoolPeriod]] = {}
    for p in all_periods:
        periods_by_day.setdefault(p.day_of_week, []).append(p)

    period_ids = {p.id for p in all_periods}
    if not period_ids:
        return []

    slots = list(await db.scalars(
        select(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.subject_id == subject_id,
            TimetableSlot.academic_year_id == academic_year_id,
            TimetableSlot.period_id.in_(period_ids),
        )
    ))
    timetabled_period_ids = {s.period_id for s in slots}
    if not timetabled_period_ids:
        return []

    period_by_id = {p.id: p for p in all_periods}

    result: list[ResolvedOccurrence] = []
    for cal in cal_days:
        weekday = _DAYS_IN_ORDER[cal.date.weekday()]
        for p in sorted(periods_by_day.get(weekday, []), key=lambda p: p.period_number):
            if p.id not in timetabled_period_ids:
                continue
            result.append(ResolvedOccurrence(
                school_calendar_id=cal.id,
                period_id=p.id,
                lesson_date=cal.date,
                start_time=period_by_id[p.id].start_time,
                end_time=period_by_id[p.id].end_time,
            ))
    return result
