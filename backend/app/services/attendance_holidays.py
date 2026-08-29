"""
Superadmin CRUD for GhanaPublicHoliday — system-wide reference data (no
school_id) that every school's generate_calendar() reads from. See
GhanaPublicHoliday's own docstring for is_recurring's exact semantics.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import GhanaPublicHoliday
from app.schemas.attendance_holidays import HolidayCreate, HolidayUpdate


async def list_holidays(db: AsyncSession) -> list[GhanaPublicHoliday]:
    rows = await db.scalars(select(GhanaPublicHoliday).order_by(GhanaPublicHoliday.date))
    return list(rows)


async def create_holiday(req: HolidayCreate, db: AsyncSession) -> GhanaPublicHoliday:
    h = GhanaPublicHoliday(
        name=req.name, date=req.date, is_recurring=req.is_recurring, description=req.description,
    )
    db.add(h)
    await db.flush()
    return h


async def _get_holiday(holiday_id: uuid.UUID, db: AsyncSession) -> GhanaPublicHoliday:
    h = await db.get(GhanaPublicHoliday, holiday_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holiday not found.")
    return h


async def update_holiday(holiday_id: uuid.UUID, req: HolidayUpdate, db: AsyncSession) -> GhanaPublicHoliday:
    h = await _get_holiday(holiday_id, db)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(h, field, value)
    await db.flush()
    return h


async def delete_holiday(holiday_id: uuid.UUID, db: AsyncSession) -> None:
    h = await _get_holiday(holiday_id, db)
    await db.delete(h)
    await db.flush()
