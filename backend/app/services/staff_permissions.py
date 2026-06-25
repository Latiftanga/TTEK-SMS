"""Personal permission overrides (StaffPermission) — Layer 1 of the 3-layer system."""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import invalidate_permissions
from app.models.auth import PositionPermission, StaffPermission
from app.models.staff import staff_member_positions
from app.schemas.auth import StaffPermissionRead, StaffPermissionUpsert

# Full catalogue — mirrors the docstring in core/permissions.py
ALL_PERMISSIONS: list[tuple[str, str]] = [
    ("school", "view"), ("school", "edit"), ("school", "manage_users"),
    ("staff", "view"), ("staff", "create"), ("staff", "edit"), ("staff", "delete"),
    ("students", "view"), ("students", "create"), ("students", "edit"), ("students", "delete"),
    ("academic", "view"), ("academic", "create"), ("academic", "edit"), ("academic", "delete"),
    ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
    ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
    ("fees", "view"), ("fees", "collect"), ("fees", "manage"),
    ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
    ("reports", "view"), ("reports", "generate"),
]


async def list_permissions(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[StaffPermissionRead]:
    """Return all 29 permissions with their resolved source for this staff member."""
    # Load position-level defaults (Layer 2)
    pos_id_rows = await db.execute(
        select(staff_member_positions.c.position_id).where(
            staff_member_positions.c.staff_member_id == staff_id
        )
    )
    position_ids = [r[0] for r in pos_id_rows]
    position_map: dict[str, bool] = {}
    if position_ids:
        pos_perms = await db.execute(
            select(PositionPermission).where(PositionPermission.position_id.in_(position_ids))
        )
        for row in pos_perms.scalars():
            key = f"{row.module}.{row.action}"
            if row.is_allowed or key not in position_map:
                position_map[key] = row.is_allowed

    # Load personal overrides (Layer 1)
    override_rows = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_member_id == staff_id,
            StaffPermission.school_id == school_id,
        )
    )
    override_map: dict[str, bool] = {
        f"{r.module}.{r.action}": r.is_allowed for r in override_rows.scalars()
    }

    result: list[StaffPermissionRead] = []
    for module, action in ALL_PERMISSIONS:
        key = f"{module}.{action}"
        if key in override_map:
            override_val = override_map[key]
            result.append(StaffPermissionRead(
                module=module, action=action,
                effective=override_val, source="override",
                override_is_allowed=override_val,
            ))
        elif key in position_map:
            result.append(StaffPermissionRead(
                module=module, action=action,
                effective=position_map[key], source="position",
            ))
        else:
            result.append(StaffPermissionRead(
                module=module, action=action,
                effective=False, source="default_deny",
            ))
    return result


async def set_permission(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    req: StaffPermissionUpsert,
    db: AsyncSession,
) -> list[StaffPermissionRead]:
    existing = await db.scalar(
        select(StaffPermission).where(
            StaffPermission.staff_member_id == staff_id,
            StaffPermission.school_id == school_id,
            StaffPermission.module == req.module,
            StaffPermission.action == req.action,
        )
    )
    if existing:
        existing.is_allowed = req.is_allowed
    else:
        db.add(StaffPermission(
            school_id=school_id,
            staff_member_id=staff_id,
            module=req.module,
            action=req.action,
            is_allowed=req.is_allowed,
        ))
    await db.flush()
    await invalidate_permissions(staff_id)
    return await list_permissions(staff_id, school_id, db)


async def clear_permission(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    module: str,
    action: str,
    db: AsyncSession,
) -> list[StaffPermissionRead]:
    result = await db.execute(
        delete(StaffPermission).where(
            StaffPermission.staff_member_id == staff_id,
            StaffPermission.school_id == school_id,
            StaffPermission.module == module,
            StaffPermission.action == action,
        ).returning(StaffPermission.id)
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="No personal override found for this permission.")
    await invalidate_permissions(staff_id)
    return await list_permissions(staff_id, school_id, db)
