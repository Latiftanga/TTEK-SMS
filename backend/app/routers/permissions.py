"""
Permission management endpoints.

GET  /permissions/positions            — list all positions with their permission matrix
PUT  /permissions/positions/{id}       — replace all permissions for a position
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, or_, select, update
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
    """Return all positions visible to this school, each with their permission matrix.

    When a school-specific position shares a code with a platform template,
    only the school-specific one is returned (it takes precedence).
    """
    _, school_id = ids
    rows = await db.scalars(
        select(StaffPosition)
        .where(or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)))
        .options(selectinload(StaffPosition.permissions))
        .order_by(StaffPosition.name)
    )
    # Deduplicate by code: school-specific wins over platform template
    seen_codes: dict[str, StaffPosition] = {}
    for pos in rows:
        existing = seen_codes.get(pos.code)
        if existing is None or pos.school_id is not None:
            seen_codes[pos.code] = pos
    return [_to_read(p) for p in sorted(seen_codes.values(), key=lambda p: p.name)]


@router.put("/positions/{position_id}", response_model=PositionWithPerms)
async def update_position_permissions(
    position_id: uuid.UUID,
    req: PositionPermissionsUpdate,
    ids: tuple = Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Replace the full permission set for a position. Invalidates all affected staff caches.

    FORK ON FIRST EDIT
    -------------------
    Most seeded positions (HEAD, TEACHER, HOD, ...) are shared platform
    templates (school_id=NULL). Editing one in place would silently change
    what that position means for every school on the platform — the same
    "shared row mutated by one tenant" bug already fixed for Programmes
    (services/academic_subjects.py::adopt_programme). So editing a template
    instead forks a school-owned copy (same code/name, school_id=this
    school) and migrates this school's own staff off the template onto the
    fork, leaving the template itself completely untouched. A school that
    already has its own copy (this call, or an earlier edit) just edits it
    in place — no repeated forking.
    """
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

    target = pos
    if pos.school_id is None:
        # Editing a shared template — reuse this school's own copy if one
        # already exists (e.g. a stale client still referencing the
        # template's id after an earlier fork), otherwise fork a new one.
        existing_fork = await db.scalar(
            select(StaffPosition)
            .where(StaffPosition.code == pos.code, StaffPosition.school_id == school_id)
            .options(selectinload(StaffPosition.permissions))
        )
        if existing_fork:
            target = existing_fork
        else:
            target = StaffPosition(
                code=pos.code, name=pos.name, school_id=school_id, is_template=False,
            )
            db.add(target)
            await db.flush()

            # Move this school's own staff off the template onto the fork —
            # otherwise their permissions wouldn't actually change, since
            # resolve_permissions() reads by the specific position_id a
            # staff member is linked to, not by code.
            staff_to_migrate = await db.scalars(
                select(staff_member_positions.c.staff_member_id)
                .join(StaffMember, StaffMember.id == staff_member_positions.c.staff_member_id)
                .where(
                    staff_member_positions.c.position_id == pos.id,
                    StaffMember.school_id == school_id,
                )
            )
            staff_ids_to_migrate = list(staff_to_migrate)
            if staff_ids_to_migrate:
                await db.execute(
                    update(staff_member_positions)
                    .where(
                        staff_member_positions.c.position_id == pos.id,
                        staff_member_positions.c.staff_member_id.in_(staff_ids_to_migrate),
                    )
                    .values(position_id=target.id)
                )

    # Replace all permission rows for the target (the fork, or the school's
    # own pre-existing row — never the shared template).
    await db.execute(
        delete(PositionPermission).where(PositionPermission.position_id == target.id)
    )
    for entry in req.permissions:
        if entry.is_allowed:  # only store granted permissions
            db.add(PositionPermission(
                position_id=target.id,
                module=entry.module,
                action=entry.action,
                is_allowed=True,
            ))

    await db.flush()
    await db.refresh(target, attribute_names=["permissions"])

    # Invalidate cache for every staff member who now holds this position
    staff_ids = await db.scalars(
        select(staff_member_positions.c.staff_member_id).where(
            staff_member_positions.c.position_id == target.id
        )
    )
    for sid in staff_ids:
        await invalidate_permissions(sid)

    return _to_read(target)
