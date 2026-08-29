"""
Bell-schedule period endpoints — the SchoolPeriod sibling of SchoolSchedule
(routers/attendance.py). Kept in its own file since routers/attendance.py is
already close to the 300-line cap.

Permission map:
  attendance.approve  → create/update/delete/copy
  attendance.view     → read (any authenticated staff)
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.attendance import PeriodCopyRequest, PeriodCreate, PeriodRead, PeriodUpdate
from app.services import school_periods as period_svc

router = APIRouter(prefix="/attendance/periods", tags=["attendance"])


@router.get("", response_model=list[PeriodRead])
async def list_periods(
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return [PeriodRead.model_validate(p) for p in await period_svc.list_periods(school_id, db)]


@router.post("", response_model=PeriodRead, status_code=201)
async def create_period(
    req: PeriodCreate,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return PeriodRead.model_validate(await period_svc.create_period(req, school_id, db))


@router.post("/copy", response_model=list[PeriodRead], status_code=201)
async def copy_periods(
    req: PeriodCopyRequest,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    created = await period_svc.copy_periods_to_days(req.source_day, req.target_days, school_id, db)
    return [PeriodRead.model_validate(p) for p in created]


@router.patch("/{period_id}", response_model=PeriodRead)
async def update_period(
    period_id: uuid.UUID,
    req: PeriodUpdate,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return PeriodRead.model_validate(await period_svc.update_period(period_id, req, school_id, db))


@router.delete("/{period_id}", status_code=204)
async def delete_period(
    period_id: uuid.UUID,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await period_svc.delete_period(period_id, school_id, db)
