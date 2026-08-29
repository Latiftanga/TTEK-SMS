"""
Superadmin CRUD for Ghana public holidays — system-wide reference data.
Every endpoint requires require_superadmin (see GhanaPublicHoliday's docstring
for why this table is managed platform-wide, not per school).
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_superadmin
from app.schemas.attendance_holidays import HolidayCreate, HolidayRead, HolidayUpdate
from app.services import attendance_holidays as holidays_svc

router = APIRouter(prefix="/superadmin/holidays", tags=["holidays"])


@router.get("", response_model=list[HolidayRead])
async def list_holidays(
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    return [HolidayRead.model_validate(h) for h in await holidays_svc.list_holidays(db)]


@router.post("", response_model=HolidayRead, status_code=201)
async def create_holiday(
    req: HolidayCreate,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    return HolidayRead.model_validate(await holidays_svc.create_holiday(req, db))


@router.patch("/{holiday_id}", response_model=HolidayRead)
async def update_holiday(
    holiday_id: uuid.UUID,
    req: HolidayUpdate,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    return HolidayRead.model_validate(await holidays_svc.update_holiday(holiday_id, req, db))


@router.delete("/{holiday_id}", status_code=204)
async def delete_holiday(
    holiday_id: uuid.UUID,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    await holidays_svc.delete_holiday(holiday_id, db)
