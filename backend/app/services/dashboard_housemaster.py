"""
Housemaster dashboard view.

A staff member can be HouseMaster for more than one house in the same year —
assign_house_master() (services/housing.py) only deactivates the *previous*
housemaster of the house being assigned, it never checks whether the
incoming staff member already runs a different house. my_houses is
therefore a list, not a single snapshot (same bug shape as TeacherDashboard's
former my_class — see services/dashboard_teacher.py).
"""
from __future__ import annotations
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.housing import Exeat, ExeatStatus, ExeatType, House, HouseMaster, StudentHouseAssignment
from app.schemas.dashboard import HouseSnapshot, HousemasterDashboard


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
        total_residents=total_residents,
        pending_exeats=pending_exeats,
        off_campus_count=off_campus,
    )


async def housemaster_view(
    school_id: uuid.UUID,
    staff_member_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> HousemasterDashboard:
    hms = (await db.scalars(
        select(HouseMaster).where(
            HouseMaster.staff_member_id == staff_member_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )).all()
    if not hms:
        return HousemasterDashboard(greeting_name=greeting_name, my_houses=[])

    house_ids = [hm.house_id for hm in hms]
    houses = (await db.scalars(select(House).where(House.id.in_(house_ids)))).all()

    my_houses = [await _house_snapshot(house, school_id, db) for house in houses]
    my_houses.sort(key=lambda h: h.name)

    return HousemasterDashboard(greeting_name=greeting_name, my_houses=my_houses)
