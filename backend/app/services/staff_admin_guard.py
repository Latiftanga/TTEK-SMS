"""Last-administrator protection — split out of services/staff.py to stay
under the 300-line cap.

Prevents a school from being left with zero staff holding school.manage_users,
whether via removing that position from a staff member's assignment or via
deactivating the staff member outright.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import StaffMember, staff_member_positions


async def _admin_position_ids(db: AsyncSession) -> set[uuid.UUID]:
    """Positions that grant school.manage_users (the admin capability)."""
    from app.models.auth import PositionPermission

    return set(await db.scalars(
        select(PositionPermission.position_id).where(
            PositionPermission.module == "school",
            PositionPermission.action == "manage_users",
            PositionPermission.is_allowed == True,
        )
    ))


async def _other_active_admins_exist(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    admin_pos_ids: set[uuid.UUID],
    db: AsyncSession,
) -> bool:
    """Whether any OTHER active staff at this school still holds an admin position."""
    count = await db.scalar(
        select(func.count(StaffMember.id.distinct())).where(
            StaffMember.school_id == school_id,
            StaffMember.id != staff_id,
            StaffMember.is_active == True,
            StaffMember.id.in_(
                select(staff_member_positions.c.staff_member_id).where(
                    staff_member_positions.c.position_id.in_(admin_pos_ids)
                )
            ),
        )
    )
    return bool(count)


async def guard_last_admin(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    new_position_ids: list[uuid.UUID],
    db: AsyncSession,
) -> None:
    """Raise 422 if this position change would leave the school with no administrator."""
    admin_pos_ids = await _admin_position_ids(db)
    if not admin_pos_ids:
        return  # no admin positions defined yet — nothing to protect

    current_pos_ids = set(await db.scalars(
        select(staff_member_positions.c.position_id).where(
            staff_member_positions.c.staff_member_id == staff_id
        )
    ))
    losing_admin = bool(current_pos_ids & admin_pos_ids) and not bool(set(new_position_ids) & admin_pos_ids)
    if not losing_admin:
        return  # this staff member isn't losing admin — nothing to check

    if not await _other_active_admins_exist(staff_id, school_id, admin_pos_ids, db):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cannot remove the administrator position: this is the only "
                "active administrator. Assign the HEAD position to another "
                "staff member first."
            ),
        )


async def guard_last_admin_deactivation(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Raise 422 if deactivating this staff member would leave the school with no administrator."""
    admin_pos_ids = await _admin_position_ids(db)
    if not admin_pos_ids:
        return

    current_pos_ids = set(await db.scalars(
        select(staff_member_positions.c.position_id).where(
            staff_member_positions.c.staff_member_id == staff_id
        )
    ))
    if not (current_pos_ids & admin_pos_ids):
        return  # this staff member isn't an admin — nothing to protect

    if not await _other_active_admins_exist(staff_id, school_id, admin_pos_ids, db):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cannot deactivate: this is the only active administrator. "
                "Assign the HEAD position to another staff member first."
            ),
        )
