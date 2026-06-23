"""
Permission management endpoints.

GET  /permissions/positions            — list all positions with their permission matrix
PUT  /permissions/positions/{id}       — replace all permissions for a position
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.permissions import invalidate_permissions, PERMISSION_CACHE_TTL_SECONDS
from app.models.auth import PositionPermission, StaffPosition
from app.models.staff import StaffMember, staff_member_positions
from app.schemas.permissions import (
    PermissionEntry, PositionWithPerms, PositionPermissionsUpdate, VALID_PAIRS,
)
from fastapi import Depends

router = APIRouter(prefix="/permissions", tags=["permissions"])


def _to_read(pos: StaffPosition) -> PositionWithPerms:
    return PositionWithPerms(
        id=pos.id,
        code=pos.code,
        name=pos.name,
        is_template=pos.is_template,
        school_id=pos.school_id,
        permissions=[
            PermissionEntry(module=p.module, action=p.action, is_allowed=p.is_allowed)
            for p in pos.permissions
            if (p.module, p.action) in VALID_PAIRS
        ],
    )


@router.get("/positions", response_model=list[PositionWithPerms])
async def list_positions_with_permissions(
    ids: tuple = Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Return all positions visible to this school, each with their permission matrix."""
    _, school_id = ids
    rows = await db.scalars(
        select(StaffPosition)
        .where(or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)))
        .options(selectinload(StaffPosition.permissions))
        .order_by(StaffPosition.name)
    )
    return [_to_read(p) for p in rows]


@router.put("/positions/{position_id}", response_model=PositionWithPerms)
async def update_position_permissions(
    position_id: uuid.UUID,
    req: PositionPermissionsUpdate,
    ids: tuple = Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Replace the full permission set for a position. Invalidates all affected staff caches."""
    _, school_id = ids

    pos = await db.scalar(
        select(StaffPosition)
        .where(
            StaffPosition.id == position_id,
            or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)),
        )
        .options(selectinload(StaffPosition.permissions))
    )
    if not pos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found.")

    # Validate that all module/action pairs are standard
    for entry in req.permissions:
        if (entry.module, entry.action) not in VALID_PAIRS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid permission: {entry.module}.{entry.action}",
            )

    # Replace all permission rows for this position
    await db.execute(
        delete(PositionPermission).where(PositionPermission.position_id == position_id)
    )
    for entry in req.permissions:
        if entry.is_allowed:  # only store granted permissions
            db.add(PositionPermission(
                position_id=position_id,
                module=entry.module,
                action=entry.action,
                is_allowed=True,
            ))

    await db.flush()
    await db.refresh(pos, attribute_names=["permissions"])

    # Invalidate cache for every staff member who holds this position
    staff_ids = await db.scalars(
        select(staff_member_positions.c.staff_member_id).where(
            staff_member_positions.c.position_id == position_id
        )
    )
    for sid in staff_ids:
        await invalidate_permissions(sid)

    return _to_read(pos)
