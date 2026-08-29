"""
Housemaster section of the composed staff dashboard — split out of
dashboard_staff.py to stay under the 300-line cap. See that module's
docstring for the overall staff_view() design.
"""
from __future__ import annotations
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.housing import Exeat, ExeatStatus, ExeatType, House, HouseMaster, StudentHouseAssignment
from app.schemas.dashboard import HouseSnapshot


async def _house_snapshot(house: House, school_id: uuid.UUID, db: AsyncSession) -> HouseSnapshot:
    total_residents = await db.scalar(
        select(func.count(StudentHouseAssignment.id)).where(
            StudentHouseAssignment.house_id == house.id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    ) or 0

    active_students = (
        select(StudentHouseAssignment.student_id).where(
            StudentHouseAssignment.house_id == house.id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    pending_exeats = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.PENDING,
            Exeat.student_id.in_(active_students),
        )
    ) or 0
    off_campus = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.APPROVED,
            Exeat.exeat_type == ExeatType.EXTERNAL,
            Exeat.student_id.in_(active_students),
        )
    ) or 0

    return HouseSnapshot(
        id=house.id,
        name=house.name,
        capacity=house.capacity,
        total_residents=total_residents,
        pending_exeats=pending_exeats,
        off_campus_count=off_campus,
    )


async def my_houses(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> list[HouseSnapshot]:
    hms = (await db.scalars(
        select(HouseMaster).where(
            HouseMaster.staff_member_id == staff_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )).all()
    if not hms:
        return []

    house_ids = [hm.house_id for hm in hms]
    houses = (await db.scalars(select(House).where(House.id.in_(house_ids)))).all()

    result = [await _house_snapshot(house, school_id, db) for house in houses]
    result.sort(key=lambda h: h.name)
    return result
