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

HOLIDAY MATCHING
----------------
GhanaPublicHoliday.is_recurring distinguishes two kinds of national holiday:
  - is_recurring=True  → a fixed-date holiday (Independence Day, Labour Day,
    Christmas, ...) that lands on the same month/day every single year. Matched
    by (month, day) across the whole term range, regardless of what year the
    seeded row was originally dated for — so a school generating a calendar for
    a year nobody ever explicitly re-seeded still correctly classifies these.
  - is_recurring=False → a moveable-date holiday (Easter/Good Friday, which
    shifts with the solar-calendar Easter computation; Eid ul-Fitr/Eid ul-Adha,
    which follow the lunar Islamic calendar) that has no fixed month/day and
    must be entered fresh for each year it's needed (via the superadmin
    holiday CRUD). Matched by exact date only.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.attendance import (
    CalendarOverrideLog, DayOfWeek, DayType, GhanaPublicHoliday, SchoolCalendar, SchoolSchedule,
)
from app.schemas.attendance import (
    CalendarDayOverride, CalendarGenerateRequest, CalendarRangeOverride, ScheduleUpsert,
)

_WEEKDAY_TO_DOW = {
    0: DayOfWeek.MON, 1: DayOfWeek.TUE, 2: DayOfWeek.WED,
    3: DayOfWeek.THU, 4: DayOfWeek.FRI, 5: DayOfWeek.SAT, 6: DayOfWeek.SUN,
}
_DEFAULT_SCHOOL_DAYS = {
    DayOfWeek.MON, DayOfWeek.TUE, DayOfWeek.WED, DayOfWeek.THU, DayOfWeek.FRI,
}


def _reject_if_term_passed(term: AcademicTerm | None) -> None:
    """A term counts as "passed" once its end_date is behind today, regardless
    of is_current — a future term (not yet started) stays fully editable, only
    a genuinely concluded one is locked. Used to block Regenerate and both
    override actions on a passed term; plain generate_calendar() deliberately
    does NOT call this — it only ever fills in missing days (never rewrites an
    existing one), so a term whose calendar was never generated at all must
    still be backfillable after the fact."""
    if term is not None and term.end_date < date.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"'{term.name}' ended on {term.end_date} — its calendar can no longer be edited.",
        )


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
        await db.flush()
        return existing
    s = SchoolSchedule(
        school_id=school_id,
        day_of_week=req.day_of_week,
        is_school_day=req.is_school_day,
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


async def _school_days_set(school_id: uuid.UUID, db: AsyncSession) -> set[DayOfWeek]:
    """The effective set of open weekdays for a school — rows marked
    is_school_day=True, falling back to Mon–Fri if the school has configured
    none at all. Single source of truth shared by generate_calendar() (which
    needs the whole set) and is_school_day() below (which just checks one
    day) — kept as one query/definition so the two can't quietly drift."""
    sched_rows = await db.scalars(
        select(SchoolSchedule).where(SchoolSchedule.school_id == school_id)
    )
    return {s.day_of_week for s in sched_rows if s.is_school_day} or _DEFAULT_SCHOOL_DAYS


async def is_school_day(day_of_week: DayOfWeek, school_id: uuid.UUID, db: AsyncSession) -> bool:
    """Whether day_of_week counts as an open school day for this school —
    used by services/school_periods.py to reject a bell period on a day
    marked closed."""
    return day_of_week in await _school_days_set(school_id, db)


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
    # force=True recomputes EXISTING days — a real rewrite of history for a
    # concluded term. Plain (non-force) generation only fills gaps, so it's
    # deliberately still allowed on a passed term (see _reject_if_term_passed).
    if req.force:
        _reject_if_term_passed(term)

    school_days = await _school_days_set(school_id, db)

    # Recurring holidays are matched by (month, day) against the WHOLE table
    # (any year they were originally seeded for), not just rows already dated
    # within this term's range — that's the whole point of "recurring": a
    # holiday seeded once for 2025 must still classify correctly in 2027.
    # Non-recurring (moveable) holidays keep the exact-date-in-range match.
    all_holiday_rows = await db.scalars(select(GhanaPublicHoliday))
    recurring_month_days: set[tuple[int, int]] = set()
    exact_holiday_dates: set[date] = set()
    for h in all_holiday_rows:
        if h.is_recurring:
            recurring_month_days.add((h.date.month, h.date.day))
        elif term.start_date <= h.date <= term.end_date:
            exact_holiday_dates.add(h.date)

    def _is_holiday(d: date) -> bool:
        return d in exact_holiday_dates or (d.month, d.day) in recurring_month_days

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
        if _is_holiday(current):
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


def _apply_override(
    cal: SchoolCalendar, day_type: DayType, notes: str | None,
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession, now: datetime,
) -> None:
    """Shared write, used by both the single-day and range override paths."""
    old_day_type = cal.day_type
    cal.day_type = day_type
    cal.notes = notes
    cal.is_manual_override = True
    db.add(CalendarOverrideLog(
        school_id=school_id,
        calendar_id=cal.id,
        old_day_type=old_day_type,
        new_day_type=day_type,
        notes=notes,
        changed_by_id=user_id,
        changed_at=now,
    ))


async def override_calendar_day(
    cal_id: uuid.UUID, req: CalendarDayOverride, school_id: uuid.UUID,
    user_id: uuid.UUID, db: AsyncSession,
) -> SchoolCalendar:
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.id == cal_id,
            SchoolCalendar.school_id == school_id,
        )
    )
    if not cal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar day not found.")
    if cal.academic_term_id is not None:
        _reject_if_term_passed(await db.get(AcademicTerm, cal.academic_term_id))
    _apply_override(cal, req.day_type, req.notes, school_id, user_id, db, datetime.now(timezone.utc))
    await db.flush()
    return cal


async def override_calendar_range(
    req: CalendarRangeOverride, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> list[SchoolCalendar]:
    """Mark every already-generated calendar day in [start_date, end_date] with
    the same day_type/notes in one action — e.g. a week-long mid-term break,
    which override_calendar_day() would otherwise need one call per day for.

    Applies unconditionally to every day found, including ones already
    is_manual_override=True — unlike generate_calendar(force=True), which
    protects manually-overridden days from an AUTOMATIC recomputation, this
    endpoint IS itself a deliberate manual override, so there's nothing to
    protect a day from here.
    """
    days = list(await db.scalars(
        select(SchoolCalendar)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date >= req.start_date,
            SchoolCalendar.date <= req.end_date,
        )
        .order_by(SchoolCalendar.date)
    ))
    if not days:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No generated calendar days found in this range — generate the "
            "calendar for the covering term first.",
        )

    # Validate every distinct term touched by this range BEFORE writing
    # anything — a range spanning a term boundary must not partially apply
    # (some days updated, others silently rejected).
    term_ids = {d.academic_term_id for d in days if d.academic_term_id is not None}
    if term_ids:
        terms = await db.scalars(select(AcademicTerm).where(AcademicTerm.id.in_(term_ids)))
        for term in terms:
            _reject_if_term_passed(term)

    now = datetime.now(timezone.utc)
    for cal in days:
        _apply_override(cal, req.day_type, req.notes, school_id, user_id, db, now)
    await db.flush()
    return days
