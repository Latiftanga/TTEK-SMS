"""
3-layer permission resolution for staff members.

LAYER SYSTEM (highest priority first)
--------------------------------------
Layer 1 — Personal override (StaffPermission table)
    An admin can grant or revoke individual permissions for a specific staff
    member.  These always beat whatever the position template says.
    Example: give a Subject Teacher access to "fees.collect" for this term.

Layer 2 — Position template (PositionPermission table)
    Default permissions inherited from the staff member's assigned position
    (e.g. HEAD, BURSAR, CLASS_TEACHER).  Applied when no personal override
    exists for a given module+action pair.

Layer 3 — Deny by default
    If neither layer 1 nor layer 2 has a rule for a given module+action,
    access is denied.  This is the secure default.

RESOLUTION EXAMPLE
------------------
Staff member Alice has position = CLASS_TEACHER.

    PositionPermission (CLASS_TEACHER):
        fees.view    = True
        fees.collect = False   ← position says NO

    StaffPermission (Alice personally):
        fees.collect = True    ← personal override says YES

    Resolved for Alice:
        fees.view    = True    (from position, no personal override)
        fees.collect = True    (personal override beats position)

CACHING
-------
Resolved permission maps are cached in Redis for 15 minutes using the key
"perms:<staff_member_id>".  The cache is invalidated immediately whenever:
  - A StaffPermission row is created, updated, or deleted for this staff member
  - The staff member's position_id is changed

Call invalidate_permissions(staff_id) after any of these operations.
Failing to do so means the old permissions stay active until the TTL expires.

MODULES AND ACTIONS (29 total across 9 modules)
-----------------------------------------------
  school:      view, edit, manage_users
  staff:       view, create, edit, delete
  students:    view, create, edit, delete
  academic:    view, create, edit, delete
  attendance:  view, record, approve
  assessments: view, enter_scores, approve_scores
  fees:        view, collect, manage
  housing:     view, assign, manage
  reports:     view, generate
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis

# How long resolved permission maps stay in Redis before being re-fetched.
# 15 minutes is a balance between freshness and DB load.
# If you need permission changes to take effect sooner, call
# invalidate_permissions() explicitly after any permission change.
PERMISSION_CACHE_TTL_SECONDS = 60 * 15

_CACHE_KEY_PREFIX = "perms:"


# ── Cache helpers (private) ───────────────────────────────────────────────────

async def _read_cache(staff_id: uuid.UUID) -> dict[str, bool] | None:
    """Return the cached permission map, or None if not cached / expired."""
    raw = await get_redis().get(f"{_CACHE_KEY_PREFIX}{staff_id}")
    return json.loads(raw) if raw else None


async def _write_cache(staff_id: uuid.UUID, perms: dict[str, bool]) -> None:
    """Store a resolved permission map in Redis."""
    await get_redis().setex(
        f"{_CACHE_KEY_PREFIX}{staff_id}",
        PERMISSION_CACHE_TTL_SECONDS,
        json.dumps(perms),
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def invalidate_permissions(staff_id: uuid.UUID) -> None:
    """
    Remove the cached permission map for a staff member.

    Call this immediately after any of:
    - Creating / updating / deleting a StaffPermission row
    - Changing a staff member's position_id

    The next request from this staff member will re-resolve from the DB
    and repopulate the cache.
    """
    await get_redis().delete(f"{_CACHE_KEY_PREFIX}{staff_id}")


async def resolve_permissions(
    staff_member_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, bool]:
    """
    Return the full permission map for a staff member.

    The map is keyed as "{module}.{action}" → bool.
    Example: {"fees.collect": True, "fees.manage": False, ...}

    Resolution order (see module docstring for details):
      1. Check Redis cache — return immediately if found.
      2. Load position-level defaults (Layer 2).
      3. Apply personal overrides on top (Layer 1).
      4. Write result back to cache.

    Args:
        staff_member_id: The staff member whose permissions to resolve.
        db: An open async DB session.

    Returns:
        A dict of all explicitly defined permissions.
        If a key is missing, the permission is denied (Layer 3 default).
    """
    # Fast path: cache hit avoids two DB round-trips on every request.
    cached = await _read_cache(staff_member_id)
    if cached is not None:
        return cached

    from app.models.auth import PositionPermission, StaffPermission
    from app.models.staff import StaffMember

    perms: dict[str, bool] = {}

    # Layer 2: load the position template defaults first.
    staff = await db.get(StaffMember, staff_member_id)
    if staff and staff.position_id:
        position_rows = await db.execute(
            select(PositionPermission).where(
                PositionPermission.position_id == staff.position_id
            )
        )
        for row in position_rows.scalars():
            perms[f"{row.module}.{row.action}"] = row.is_allowed

    # Layer 1: apply personal overrides — these always win.
    override_rows = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_member_id == staff_member_id
        )
    )
    for row in override_rows.scalars():
        perms[f"{row.module}.{row.action}"] = row.is_allowed

    await _write_cache(staff_member_id, perms)
    return perms


async def has_permission(
    staff_member_id: uuid.UUID,
    module: str,
    action: str,
    db: AsyncSession,
) -> bool:
    """
    Convenience function: return True if the staff member has a specific permission.

    Uses the same cache as resolve_permissions, so calling this repeatedly in
    one request is cheap after the first call.
    """
    perms = await resolve_permissions(staff_member_id, db)
    return perms.get(f"{module}.{action}", False)
