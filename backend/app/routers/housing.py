"""Housing router — houses, rooms, housemasters, student assignments, roll calls, exeats.

ROUTE ORDER NOTE
----------------
/exeats/pending is declared before /exeats/{exeat_id}/... to prevent path capture.
/students/{student_id}/assignment and /students/{student_id}/exeats use different
literal final segments so ordering is not an issue there.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.schemas.housing import (
    AssignmentCreate, AssignmentRead, AssignmentVacate,
    ExeatApprove, ExeatCreate, ExeatRead, ExeatReturn,
    HouseCreate, HouseDetail, HouseMasterAssign, HouseMasterRead, HouseUpdate,
    RollCallCreate, RollCallRead,
    RoomCreate, RoomRead, RoomUpdate,
)
from app.services import housing as svc
from app.services import housing_events as event_svc


async def _require_boarding(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Block all housing endpoints for schools that have not enabled boarding."""
    from app.models.school import School
    _, school_id = ids
    if school_id is None:
        return
    school = await db.get(School, school_id)
    if not school or not school.has_boarding:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This school does not have boarding facilities enabled.",
        )


router = APIRouter(
    prefix="/housing",
    tags=["housing"],
    dependencies=[Depends(_require_boarding)],
)


# ── Houses ────────────────────────────────────────────────────────────────────

@router.post("/houses", response_model=HouseDetail, status_code=201)
async def create_house(
    req: HouseCreate,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.create_house(req, school_id, db)


@router.get("/houses", response_model=list[HouseDetail])
async def list_houses(
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.list_houses(school_id, db)


@router.get("/houses/{house_id}", response_model=HouseDetail)
async def get_house(
    house_id: uuid.UUID,
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.get_house(house_id, school_id, db)


@router.patch("/houses/{house_id}", response_model=HouseDetail)
async def update_house(
    house_id: uuid.UUID,
    req: HouseUpdate,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.update_house(house_id, req, school_id, db)


# ── Rooms ─────────────────────────────────────────────────────────────────────

@router.post("/houses/{house_id}/rooms", response_model=RoomRead, status_code=201)
async def add_room(
    house_id: uuid.UUID,
    req: RoomCreate,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.add_room(house_id, req, school_id, db)


@router.get("/houses/{house_id}/rooms", response_model=list[RoomRead])
async def list_rooms(
    house_id: uuid.UUID,
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.list_rooms(house_id, school_id, db)


@router.patch("/houses/{house_id}/rooms/{room_id}", response_model=RoomRead)
async def update_room(
    house_id: uuid.UUID,
    room_id: uuid.UUID,
    req: RoomUpdate,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.update_room(house_id, room_id, req, school_id, db)


# ── HouseMaster ───────────────────────────────────────────────────────────────

@router.post("/houses/{house_id}/master", response_model=HouseMasterRead, status_code=201)
async def assign_house_master(
    house_id: uuid.UUID,
    req: HouseMasterAssign,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.assign_house_master(house_id, req, school_id, db)


@router.get("/houses/{house_id}/master", response_model=HouseMasterRead | None)
async def get_house_master(
    house_id: uuid.UUID,
    year_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.get_current_house_master(house_id, year_id, school_id, db)


# ── Student assignments ───────────────────────────────────────────────────────

@router.post("/assignments", response_model=AssignmentRead, status_code=201)
async def assign_student(
    req: AssignmentCreate,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.assign_student(req, school_id, db)


@router.patch("/assignments/{assignment_id}/vacate", response_model=AssignmentRead)
async def vacate_assignment(
    assignment_id: uuid.UUID,
    req: AssignmentVacate,
    ids=Depends(require_permission("housing", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.vacate_assignment(assignment_id, req, school_id, db)


@router.get("/students/{student_id}/assignment", response_model=AssignmentRead | None)
async def get_student_assignment(
    student_id: uuid.UUID,
    year_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.get_student_current_assignment(student_id, year_id, school_id, db)


# ── Roll calls ────────────────────────────────────────────────────────────────

@router.post("/roll-calls", response_model=RollCallRead, status_code=201)
async def record_roll_call(
    req: RollCallCreate,
    ids=Depends(require_permission("housing", "roll_call")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await event_svc.record_roll_call(req, school_id, user_id, db)


@router.get("/roll-calls", response_model=list[RollCallRead])
async def list_roll_calls(
    house_id: uuid.UUID = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await event_svc.list_roll_calls(house_id, school_id, db, skip=skip, limit=limit)


# ── Exeats (pending before /{exeat_id} to prevent path capture) ───────────────

@router.post("/exeats", response_model=ExeatRead, status_code=201)
async def create_exeat(
    req: ExeatCreate,
    ids=Depends(require_permission("housing", "manage_exeats")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await event_svc.create_exeat(req, school_id, db)


@router.get("/exeats/pending", response_model=list[ExeatRead])
async def list_pending_exeats(
    ids=Depends(require_permission("housing", "manage_exeats")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await event_svc.list_pending_exeats(school_id, db)


@router.patch("/exeats/{exeat_id}/approve", response_model=ExeatRead)
async def review_exeat(
    exeat_id: uuid.UUID,
    req: ExeatApprove,
    ids=Depends(require_permission("housing", "manage_exeats")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await event_svc.review_exeat(exeat_id, req, school_id, user_id, db)


@router.patch("/exeats/{exeat_id}/return", response_model=ExeatRead)
async def record_return(
    exeat_id: uuid.UUID,
    req: ExeatReturn,
    ids=Depends(require_permission("housing", "manage_exeats")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await event_svc.record_return(exeat_id, req, school_id, db)


@router.get("/students/{student_id}/exeats", response_model=list[ExeatRead])
async def list_student_exeats(
    student_id: uuid.UUID,
    ids=Depends(require_permission("housing", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await event_svc.list_student_exeats(student_id, school_id, db)
