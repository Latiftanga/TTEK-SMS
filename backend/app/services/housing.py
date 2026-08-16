from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.housing_scope import assert_house_in_scope, assert_unrestricted, current_year_id, resolve_house_scope
from app.models.academic import AcademicYear
from app.models.housing import House, HouseMaster, Room
from app.models.staff import StaffMember
from app.schemas.housing import (
    HouseCreate, HouseDetail, HouseMasterAssign, HouseMasterRead, HouseUpdate,
    RoomCreate, RoomRead, RoomUpdate,
)


def _to_room(r: Room) -> RoomRead:
    return RoomRead.model_validate(r)


def _to_detail(h: House) -> HouseDetail:
    d = HouseDetail.model_validate(h)
    d.rooms = [_to_room(r) for r in (h.rooms or [])]
    return d


def _to_hm(hm: HouseMaster) -> HouseMasterRead:
    return HouseMasterRead.model_validate(hm)


async def _fetch_house(
    house_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> House:
    h = await db.scalar(
        select(House)
        .where(House.id == house_id, House.school_id == school_id)
        .options(selectinload(House.rooms))
    )
    if not h:
        raise HTTPException(404, "House not found.")
    year_id = await current_year_id(school_id, db)
    await assert_house_in_scope(house_id, user_id, school_id, year_id, db)
    return h


async def create_house(
    req: HouseCreate, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> HouseDetail:
    year_id = await current_year_id(school_id, db)
    await assert_unrestricted(
        user_id, school_id, year_id, db,
        "Only a school administrator can create a new house.",
    )
    house = House(
        school_id=school_id,
        name=req.name,
        code=req.code.upper(),
        gender=req.gender,
        capacity=req.capacity,
        color=req.color,
        is_active=True,
    )
    try:
        async with db.begin_nested():
            db.add(house)
            await db.flush()
    except IntegrityError:
        raise HTTPException(409, f"A house with code '{req.code.upper()}' already exists at this school.")
    await db.refresh(house, attribute_names=["rooms"])
    return _to_detail(house)


async def list_houses(user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> list[HouseDetail]:
    """Every house for an unrestricted caller (anyone who isn't an active
    HouseMaster this year); only the house(s) the caller is an active
    HouseMaster of this year otherwise. GET /houses and GET /houses/mine are
    the same scoped query — /mine exists only as a clearer name for the
    housemaster-facing frontend, not a different access level."""
    year_id = await current_year_id(school_id, db)
    scope = await resolve_house_scope(user_id, school_id, year_id, db)
    q = select(House).where(House.school_id == school_id).options(selectinload(House.rooms))
    if scope is not None:
        q = q.where(House.id.in_(scope))
    rows = (await db.scalars(q.order_by(House.name))).all()
    return [_to_detail(h) for h in rows]


async def get_house(
    house_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> HouseDetail:
    return _to_detail(await _fetch_house(house_id, user_id, school_id, db))


async def update_house(
    house_id: uuid.UUID, req: HouseUpdate, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> HouseDetail:
    house = await _fetch_house(house_id, user_id, school_id, db)
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(house, k, v)
    await db.flush()
    return _to_detail(house)


async def add_room(
    house_id: uuid.UUID, req: RoomCreate, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> RoomRead:
    await _fetch_house(house_id, user_id, school_id, db)
    room = Room(
        school_id=school_id,
        house_id=house_id,
        room_number=req.room_number,
        capacity=req.capacity,
        room_type=req.room_type,
    )
    db.add(room)
    await db.flush()
    return _to_room(room)


async def list_rooms(
    house_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[RoomRead]:
    await _fetch_house(house_id, user_id, school_id, db)
    rows = (await db.scalars(
        select(Room)
        .where(Room.house_id == house_id, Room.school_id == school_id)
        .order_by(Room.room_number)
    )).all()
    return [_to_room(r) for r in rows]


async def update_room(
    house_id: uuid.UUID, room_id: uuid.UUID, req: RoomUpdate,
    user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> RoomRead:
    await _fetch_house(house_id, user_id, school_id, db)
    room = await db.scalar(
        select(Room).where(
            Room.id == room_id,
            Room.house_id == house_id,
            Room.school_id == school_id,
        )
    )
    if not room:
        raise HTTPException(404, "Room not found.")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(room, k, v)
    await db.flush()
    return _to_room(room)


async def assign_house_master(
    house_id: uuid.UUID, req: HouseMasterAssign, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> HouseMasterRead:
    # Deciding WHO manages a house is an administrative appointment, not
    # day-to-day house management — even a caller who already manages a
    # different house can't reassign themselves or anyone else.
    await assert_unrestricted(
        user_id, school_id, req.academic_year_id, db,
        "Only a school administrator can assign a housemaster.",
    )
    house = await db.scalar(select(House).where(House.id == house_id, House.school_id == school_id))
    if not house:
        raise HTTPException(404, "House not found.")
    staff = await db.scalar(
        select(StaffMember).where(
            StaffMember.id == req.staff_member_id,
            StaffMember.school_id == school_id,
        )
    )
    if not staff:
        raise HTTPException(404, "Staff member not found.")
    year = await db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == req.academic_year_id,
            AcademicYear.school_id == school_id,
        )
    )
    if not year:
        raise HTTPException(404, "Academic year not found.")
    existing = (await db.scalars(
        select(HouseMaster).where(
            HouseMaster.house_id == house_id,
            HouseMaster.academic_year_id == req.academic_year_id,
            HouseMaster.is_active.is_(True),
        )
    )).all()
    for hm in existing:
        hm.is_active = False
    hm = HouseMaster(
        school_id=school_id,
        house_id=house_id,
        staff_member_id=req.staff_member_id,
        academic_year_id=req.academic_year_id,
        is_active=True,
    )
    db.add(hm)
    await db.flush()
    return _to_hm(hm)


async def get_current_house_master(
    house_id: uuid.UUID, year_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> HouseMasterRead | None:
    await assert_house_in_scope(house_id, user_id, school_id, year_id, db)
    hm = await db.scalar(
        select(HouseMaster).where(
            HouseMaster.house_id == house_id,
            HouseMaster.academic_year_id == year_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )
    return _to_hm(hm) if hm else None
