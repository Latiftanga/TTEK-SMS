"""
School schedule management and calendar day generation.

CALENDAR GENERATION LOGIC
--------------------------
For a given term, iterates every date between term.start_date and term.end_date:
  - Days in the school schedule with is_school_day=True → SCHOOL_DAY
  - Dates matching a GhanaPublicHoliday → PUBLIC_HOLIDAY (beats schedule)
  - All other days → WEEKEND (Saturday/Sunday) or left as not-school days

If no SchoolSchedule rows exist for the school, Mon–Fri is assumed as the default.
Existing calendar entries for a date are never overwritten by generation — re-run is idempotent.
"""
from __future__ import annotations
import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.attendance import (
    DayOfWeek, DayType, GhanaPublicHoliday, SchoolCalendar, SchoolSchedule,
)
from app.schemas.attendance import CalendarDayOverride, CalendarGenerateRequest, ScheduleUpsert

_WEEKDAY_TO_DOW = {
    0: DayOfWeek.MON, 1: DayOfWeek.TUE, 2: DayOfWeek.WED,
    3: DayOfWeek.THU, 4: DayOfWeek.FRI, 5: DayOfWeek.SAT, 6: DayOfWeek.SUN,
}
_DEFAULT_SCHOOL_DAYS = {
    DayOfWeek.MON, DayOfWeek.TUE, DayOfWeek.WED, DayOfWeek.THU, DayOfWeek.FRI,
}


async def upsert_schedule(
    req: ScheduleUpsert, school_id: uuid.UUID, db: AsyncSession
) -> SchoolSchedule:
    existing = await db.scalar(
        select(SchoolSchedule).where(
            SchoolSchedule.school_id == school_id,
            SchoolSchedule.day_of_week == req.day_of_week,
        )
    )
    if existing:
        existing.is_school_day = req.is_school_day
        existing.start_time = req.start_time
        existing.end_time = req.end_time
        await db.flush()
        return existing
    s = SchoolSchedule(
        school_id=school_id,
        day_of_week=req.day_of_week,
        is_school_day=req.is_school_day,
        start_time=req.start_time,
        end_time=req.end_time,
    )
    db.add(s)
    await db.flush()
    return s


async def list_schedule(school_id: uuid.UUID, db: AsyncSession) -> list[SchoolSchedule]:
    rows = await db.scalars(
        select(SchoolSchedule)
        .where(SchoolSchedule.school_id == school_id)
        .order_by(SchoolSchedule.day_of_week)
    )
    return list(rows)


async def generate_calendar(
    req: CalendarGenerateRequest, school_id: uuid.UUID, db: AsyncSession
) -> list[SchoolCalendar]:
    term = await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == req.term_id, AcademicTerm.school_id == school_id,
        )
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")

    sched_rows = await db.scalars(
        select(SchoolSchedule).where(SchoolSchedule.school_id == school_id)
    )
    school_days = {s.day_of_week for s in sched_rows if s.is_school_day} or _DEFAULT_SCHOOL_DAYS

    holiday_rows = await db.scalars(
        select(GhanaPublicHoliday).where(
            GhanaPublicHoliday.date >= term.start_date,
            GhanaPublicHoliday.date <= term.end_date,
        )
    )
    holiday_dates: set[date] = {h.date for h in holiday_rows}

    # Fetch dates already in the calendar for this term (skip them)
    existing_dates_rows = await db.scalars(
        select(SchoolCalendar.date).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == req.term_id,
        )
    )
    existing_dates: set[date] = set(existing_dates_rows)

    created: list[SchoolCalendar] = []
    current = term.start_date
    while current <= term.end_date:
        if current not in existing_dates:
            dow = _WEEKDAY_TO_DOW[current.weekday()]
            if current in holiday_dates:
                day_type = DayType.PUBLIC_HOLIDAY
            elif dow in school_days:
                day_type = DayType.SCHOOL_DAY
            else:
                day_type = DayType.WEEKEND
            cal = SchoolCalendar(
                school_id=school_id,
                date=current,
                day_type=day_type,
                academic_term_id=req.term_id,
            )
            db.add(cal)
            created.append(cal)
        current += timedelta(days=1)

    await db.flush()
    return created


async def list_calendar(
    school_id: uuid.UUID, term_id: uuid.UUID, db: AsyncSession
) -> list[SchoolCalendar]:
    rows = await db.scalars(
        select(SchoolCalendar)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
        )
        .order_by(SchoolCalendar.date)
    )
    return list(rows)


async def override_calendar_day(
    cal_id: uuid.UUID, req: CalendarDayOverride, school_id: uuid.UUID, db: AsyncSession
) -> SchoolCalendar:
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.id == cal_id,
            SchoolCalendar.school_id == school_id,
        )
    )
    if not cal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar day not found.")
    cal.day_type = req.day_type
    cal.notes = req.notes
    await db.flush()
    return cal
