"""
Bell-schedule period CRUD — reactivates SchoolPeriod (models/attendance.py),
which was fully modeled but had zero code anywhere touching it until now.

Periods are day-specific (a school's Monday bell times can differ from
Friday's — the model's own uq_school_period constraint is per day_of_week),
so most schools will want identical periods on several days at once;
copy_periods_to_days() exists to avoid hand-entering the same 8 periods five
times over.
"""
from __future__ import annotations
import uuid
from datetime import time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import DayOfWeek, SchoolPeriod
from app.schemas.attendance import PeriodCreate, PeriodUpdate
from app.services.attendance_calendar import is_school_day as _is_school_day


def _validate_times(start_time: time, end_time: time) -> None:
    if end_time <= start_time:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "end_time must be after start_time."
        )


async def _assert_unique(
    school_id: uuid.UUID,
    day_of_week: DayOfWeek,
    name: str,
    start_time: time,
    end_time: time,
    db: AsyncSession,
    *,
    exclude_period_id: uuid.UUID | None = None,
) -> None:
    """Within the same school+day, name/start_time/end_time must each be
    unique — a clean, specific 409 ahead of the matching DB-level
    constraints (uq_school_period_name/_start/_end), which stay as the race
    safety net. Scoped per day, not school-wide — the same name/start/end
    repeating on a different day (e.g. via copy_periods_to_days) is normal."""
    stmt = select(SchoolPeriod).where(
        SchoolPeriod.school_id == school_id, SchoolPeriod.day_of_week == day_of_week,
    )
    if exclude_period_id is not None:
        stmt = stmt.where(SchoolPeriod.id != exclude_period_id)
    for sib in await db.scalars(stmt):
        if sib.name == name:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"A period named '{name}' already exists for {day_of_week.value}.",
            )
        if sib.start_time == start_time:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"A period already starts at {start_time.strftime('%H:%M')} on {day_of_week.value}.",
            )
        if sib.end_time == end_time:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"A period already ends at {end_time.strftime('%H:%M')} on {day_of_week.value}.",
            )


async def list_periods(school_id: uuid.UUID, db: AsyncSession) -> list[SchoolPeriod]:
    rows = await db.scalars(
        select(SchoolPeriod)
        .where(SchoolPeriod.school_id == school_id)
        .order_by(SchoolPeriod.day_of_week, SchoolPeriod.period_number)
    )
    return list(rows)


async def create_period(
    req: PeriodCreate, school_id: uuid.UUID, db: AsyncSession
) -> SchoolPeriod:
    _validate_times(req.start_time, req.end_time)
    if not await _is_school_day(req.day_of_week, school_id, db):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{req.day_of_week.value} is not marked as a school day — "
            "open it on the Attendance Schedule page first.",
        )
    name = req.name.strip()
    await _assert_unique(school_id, req.day_of_week, name, req.start_time, req.end_time, db)
    period = SchoolPeriod(
        school_id=school_id,
        name=name,
        day_of_week=req.day_of_week,
        period_number=req.period_number,
        start_time=req.start_time,
        end_time=req.end_time,
    )
    db.add(period)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Period {req.period_number} already exists for {req.day_of_week.value}.",
        )
    return period


async def _get_owned(period_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> SchoolPeriod:
    period = await db.get(SchoolPeriod, period_id)
    if not period or period.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Period not found.")
    return period


async def update_period(
    period_id: uuid.UUID, req: PeriodUpdate, school_id: uuid.UUID, db: AsyncSession
) -> SchoolPeriod:
    period = await _get_owned(period_id, school_id, db)
    new_start = req.start_time if req.start_time is not None else period.start_time
    new_end = req.end_time if req.end_time is not None else period.end_time
    new_name = req.name.strip() if req.name is not None else period.name
    _validate_times(new_start, new_end)
    await _assert_unique(
        school_id, period.day_of_week, new_name, new_start, new_end, db,
        exclude_period_id=period.id,
    )
    period.name = new_name
    period.start_time = new_start
    period.end_time = new_end
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"That name/start/end conflicts with another period on {period.day_of_week.value}.",
        )
    return period


async def delete_period(period_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    period = await _get_owned(period_id, school_id, db)
    await db.delete(period)
    await db.flush()


async def copy_periods_to_days(
    source_day: DayOfWeek,
    target_days: list[DayOfWeek],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SchoolPeriod]:
    """Skips any (target_day, period_number) that already exists, any clone
    whose name/start_time/end_time would collide with a period already on
    the target day, and any target_day marked closed on SchoolSchedule,
    rather than erroring the whole batch — safe to re-run after a partial
    edit. Unlike create_period (one explicit day, hard rejected), all of
    these are silently excluded from the batch here."""
    source_periods = list(await db.scalars(
        select(SchoolPeriod).where(
            SchoolPeriod.school_id == school_id, SchoolPeriod.day_of_week == source_day,
        )
    ))
    if not source_periods:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No periods defined for {source_day.value} to copy.",
        )

    created: list[SchoolPeriod] = []
    for target_day in target_days:
        if target_day == source_day:
            continue
        if not await _is_school_day(target_day, school_id, db):
            continue
        target_periods = list(await db.scalars(
            select(SchoolPeriod).where(
                SchoolPeriod.school_id == school_id, SchoolPeriod.day_of_week == target_day,
            )
        ))
        existing_numbers = {p.period_number for p in target_periods}
        existing_names = {p.name for p in target_periods}
        existing_starts = {p.start_time for p in target_periods}
        existing_ends = {p.end_time for p in target_periods}
        for sp in source_periods:
            if (
                sp.period_number in existing_numbers
                or sp.name in existing_names
                or sp.start_time in existing_starts
                or sp.end_time in existing_ends
            ):
                continue
            clone = SchoolPeriod(
                school_id=school_id,
                name=sp.name,
                day_of_week=target_day,
                period_number=sp.period_number,
                start_time=sp.start_time,
                end_time=sp.end_time,
            )
            db.add(clone)
            created.append(clone)
    await db.flush()
    return created
