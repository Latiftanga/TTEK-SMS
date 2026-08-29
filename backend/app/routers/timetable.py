"""
Class timetable + "what do I teach tomorrow" endpoints. Kept separate from
academic_structure.py, which is already at the 300-line cap.

Permission map:
  academic.view / academic.edit  → class timetable read / write
  assessments.view               → GET /timetable/my-schedule, matching
                                    GET /assessments/my-subjects' own tier
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.timetable import ScheduleEntry, TimetableSlotRead, TimetableSlotUpsert
from app.services import timetable as tt_svc

router = APIRouter(tags=["timetable"])


@router.get("/academic/classes/{class_id}/timetable", response_model=list[TimetableSlotRead])
async def get_class_timetable(
    class_id: uuid.UUID,
    year_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("academic", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await tt_svc.get_class_timetable(class_id, year_id, school_id, db)


@router.put("/academic/classes/{class_id}/timetable/{period_id}", response_model=TimetableSlotRead)
async def upsert_timetable_slot(
    class_id: uuid.UUID,
    period_id: uuid.UUID,
    req: TimetableSlotUpsert,
    year_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await tt_svc.upsert_timetable_slot(class_id, period_id, req, year_id, school_id, db)


@router.delete("/academic/classes/{class_id}/timetable/{period_id}", status_code=204)
async def delete_timetable_slot(
    class_id: uuid.UUID,
    period_id: uuid.UUID,
    year_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await tt_svc.delete_timetable_slot(class_id, period_id, year_id, school_id, db)


@router.get("/timetable/my-schedule", response_model=list[ScheduleEntry])
async def get_my_schedule(
    year_id: uuid.UUID | None = Query(None),
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    """The caller's own full weekly schedule — every day at once, since a
    timetable is a recurring structure. Defaults to the school's current
    academic year when year_id is omitted."""
    user_id, school_id = ids
    return await tt_svc.resolve_my_schedule(user_id, year_id, school_id, db)
