from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear
from app.models.housing import House, HouseMaster, Room, StudentHouseAssignment
from app.models.staff import StaffMember
from app.models.students import Student
from app.schemas.housing import (
    AssignmentCreate, AssignmentRead, AssignmentVacate,
    HouseCreate, HouseDetail, HouseMasterAssign, HouseMasterRead, HouseUpdate,
    RoomCreate, RoomRead, RoomUpdate,
)


def _to_room(r: Room) -> RoomRead:
    return RoomRead.model_validate(r)


def _to_detail(h: House) -> HouseDetail:
    d = HouseDetail.model_validate(h)
    d.rooms = [_to_room(r) for r in (h.rooms or [])]
    return d


def _to_assignment(a: StudentHouseAssignment) -> AssignmentRead:
    return AssignmentRead.model_validate(a)


def _to_hm(hm: HouseMaster) -> HouseMasterRead:
    return HouseMasterRead.model_validate(hm)


async def _fetch_house(house_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> House:
    h = await db.scalar(
        select(House)
        .where(House.id == house_id, House.school_id == school_id)
        .options(selectinload(House.rooms))
    )
    if not h:
        raise HTTPException(404, "House not found.")
    return h


async def create_house(req: HouseCreate, school_id: uuid.UUID, db: AsyncSession) -> HouseDetail:
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


async def list_houses(school_id: uuid.UUID, db: AsyncSession) -> list[HouseDetail]:
    rows = (await db.scalars(
        select(House)
        .where(House.school_id == school_id)
        .options(selectinload(House.rooms))
        .order_by(House.name)
    )).all()
    return [_to_detail(h) for h in rows]


async def get_house(house_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> HouseDetail:
    return _to_detail(await _fetch_house(house_id, school_id, db))


async def update_house(
    house_id: uuid.UUID, req: HouseUpdate, school_id: uuid.UUID, db: AsyncSession
) -> HouseDetail:
    house = await _fetch_house(house_id, school_id, db)
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(house, k, v)
    await db.flush()
    return _to_detail(house)


async def add_room(
    house_id: uuid.UUID, req: RoomCreate, school_id: uuid.UUID, db: AsyncSession
) -> RoomRead:
    await _fetch_house(house_id, school_id, db)
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
    house_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[RoomRead]:
    await _fetch_house(house_id, school_id, db)
    rows = (await db.scalars(
        select(Room)
        .where(Room.house_id == house_id, Room.school_id == school_id)
        .order_by(Room.room_number)
    )).all()
    return [_to_room(r) for r in rows]


async def update_room(
    house_id: uuid.UUID, room_id: uuid.UUID, req: RoomUpdate,
    school_id: uuid.UUID, db: AsyncSession,
) -> RoomRead:
    await _fetch_house(house_id, school_id, db)
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
    house_id: uuid.UUID, req: HouseMasterAssign, school_id: uuid.UUID, db: AsyncSession
) -> HouseMasterRead:
    await _fetch_house(house_id, school_id, db)
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
    house_id: uuid.UUID, year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> HouseMasterRead | None:
    hm = await db.scalar(
        select(HouseMaster).where(
            HouseMaster.house_id == house_id,
            HouseMaster.academic_year_id == year_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )
    return _to_hm(hm) if hm else None


async def assign_student(req: AssignmentCreate, school_id: uuid.UUID, db: AsyncSession) -> AssignmentRead:
    student = await db.scalar(
        select(Student).where(Student.id == req.student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    house = await db.scalar(
        select(House).where(House.id == req.house_id, House.school_id == school_id)
    )
    if not house:
        raise HTTPException(404, "House not found.")
    if req.room_id:
        room = await db.scalar(
            select(Room).where(
                Room.id == req.room_id,
                Room.house_id == req.house_id,
                Room.school_id == school_id,
            )
        )
        if not room:
            raise HTTPException(404, "Room not found in this house.")
    existing = await db.scalar(
        select(StudentHouseAssignment).where(
            StudentHouseAssignment.student_id == req.student_id,
            StudentHouseAssignment.academic_year_id == req.academic_year_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    if existing:
        raise HTTPException(409, "Student already has an active house assignment for this academic year.")
    assignment = StudentHouseAssignment(
        school_id=school_id,
        student_id=req.student_id,
        house_id=req.house_id,
        room_id=req.room_id,
        academic_year_id=req.academic_year_id,
        assigned_at=req.assigned_at,
    )
    db.add(assignment)
    await db.flush()
    return _to_assignment(assignment)


async def vacate_assignment(
    assignment_id: uuid.UUID, req: AssignmentVacate, school_id: uuid.UUID, db: AsyncSession
) -> AssignmentRead:
    assignment = await db.scalar(
        select(StudentHouseAssignment).where(
            StudentHouseAssignment.id == assignment_id,
            StudentHouseAssignment.school_id == school_id,
        )
    )
    if not assignment:
        raise HTTPException(404, "Assignment not found.")
    if assignment.vacated_at:
        raise HTTPException(409, "Assignment is already vacated.")
    if req.vacated_at < assignment.assigned_at:
        raise HTTPException(422, "vacated_at must be on or after assigned_at.")
    assignment.vacated_at = req.vacated_at
    await db.flush()
    return _to_assignment(assignment)


async def get_student_current_assignment(
    student_id: uuid.UUID, year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> AssignmentRead | None:
    assignment = await db.scalar(
        select(StudentHouseAssignment).where(
            StudentHouseAssignment.student_id == student_id,
            StudentHouseAssignment.academic_year_id == year_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    return _to_assignment(assignment) if assignment else None
