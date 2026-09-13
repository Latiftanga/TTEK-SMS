"""
Class timetable + "what do I teach tomorrow" endpoints. Kept separate from
academic_structure.py, which is already at the 300-line cap.

Permission map:
  academic.view / academic.edit  → class timetable read / write, including
                                    the whole-school bulk CSV import below
  assessments.view               → GET /timetable/my-schedule, matching
                                    GET /assessments/my-subjects' own tier
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.documents import ImportBatchResult
from app.schemas.timetable import ScheduleEntry, TimetableSlotRead, TimetableSlotUpsert
from app.services import timetable as tt_svc
from app.services import timetable_import as tt_import_svc

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


@router.post("/academic/timetable/import", response_model=ImportBatchResult)
async def import_timetable(
    year_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-create/update a school's TimetableSlot rows for one academic
    year from a FET (Free Timetabling Software) CSV export — whole-school
    in one pass, since FET solves and exports the entire timetable at once.
    Best-effort like /staff/import: valid rows are created, invalid or
    conflicting rows are reported per-row rather than aborting the batch."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Only .csv files are accepted.")
    user_id, school_id = ids
    file_bytes = await file.read()
    return await tt_import_svc.process_import(file_bytes, school_id, year_id, user_id, db)


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
