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

force=True recomputes every day against the current schedule/holidays, EXCEPT a day
with is_manual_override=True (set by override_calendar_day) — a staff member's manual
correction always survives a force-regeneration.
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

    # school_calendar is uniquely constrained on (school_id, date) — ONE row per
    # school per date, school-wide, not per-term (a calendar date can only ever
    # belong to one term). Scoping this lookup to req.term_id (as before) missed
    # rows already claimed by a *different* term whose date range happens to
    # overlap this one — generation would then try to INSERT a duplicate for
    # that date and crash with a raw IntegrityError instead of a clear message.
    existing_rows = await db.scalars(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date >= term.start_date,
            SchoolCalendar.date <= term.end_date,
        )
    )
    existing_map: dict[date, SchoolCalendar] = {r.date: r for r in existing_rows}

    # Validate before writing anything — two terms with overlapping date ranges
    # is a data problem to fix at the source (the term dates), not something to
    # silently paper over by skipping days or stealing them from the other term
    # (which would orphan any AttendanceRecord already marked against them).
    conflict_term_ids = {
        r.academic_term_id for r in existing_map.values() if r.academic_term_id != req.term_id
    }
    if conflict_term_ids:
        other_terms = await db.scalars(select(AcademicTerm).where(AcademicTerm.id.in_(conflict_term_ids)))
        names = ", ".join(sorted({t.name for t in other_terms}))
        conflict_dates = sorted(
            d for d, r in existing_map.items() if r.academic_term_id in conflict_term_ids
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{len(conflict_dates)} day(s) in this term's range ({conflict_dates[0]} to "
            f"{conflict_dates[-1]}) already belong to another term's calendar ({names}) — "
            "their date ranges overlap. Fix the term dates so they don't overlap, then "
            "generate the calendar again.",
        )

    touched: list[SchoolCalendar] = []
    current = term.start_date
    while current <= term.end_date:
        dow = _WEEKDAY_TO_DOW[current.weekday()]
        if current in holiday_dates:
            day_type = DayType.PUBLIC_HOLIDAY
        elif dow in school_days:
            day_type = DayType.SCHOOL_DAY
        else:
            day_type = DayType.WEEKEND

        if current in existing_map:
            if req.force and not existing_map[current].is_manual_override:
                # Update in-place — preserves the row ID so AttendanceRecord FKs survive.
                # A manually-overridden day (see override_calendar_day) is left
                # untouched even under force — it's not appended to `touched`.
                existing_map[current].day_type = day_type
                touched.append(existing_map[current])
        else:
            cal = SchoolCalendar(
                school_id=school_id,
                date=current,
                day_type=day_type,
                academic_term_id=req.term_id,
            )
            db.add(cal)
            touched.append(cal)
        current += timedelta(days=1)

    await db.flush()
    return touched


async def list_calendar(
    school_id: uuid.UUID, term_id: uuid.UUID, db: AsyncSession
) -> list[SchoolCalendar]:
    term = await db.scalar(
        select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")
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
    cal.is_manual_override = True
    await db.flush()
    return cal
