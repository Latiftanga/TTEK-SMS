"""
3-layer permission resolution for staff members.

LAYER SYSTEM (highest priority first)
--------------------------------------
Layer 1 — Personal override (StaffPermission table)
    An admin can grant or revoke individual permissions for a specific staff
    member.  These always beat whatever the position template says.
    Example: give a Subject Teacher access to "fees.collect" for this term.

Layer 2 — Position templates (PositionPermission table)
    Permissions are unioned across ALL positions the staff member holds
    (e.g. a TEACHER who is also a HOUSE_MASTER gets both sets).
    Applied when no personal override exists for a given module+action pair.

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

MODULES AND ACTIONS (32 total across 10 modules)
-----------------------------------------------
  school:      view, edit, manage_users
  staff:       view, create, edit, delete
  students:    view, create, edit, delete
  academic:    view, create, edit, delete
  attendance:  view, record, approve
  assessments: view, enter_scores, approve_scores, record_behaviour
  fees:        view, collect, manage
  housing:     view, assign, manage
  reports:     view, generate
  documents:   view, manage

The canonical list lives in schemas/permissions.py::PERMISSION_MATRIX — this
docstring is descriptive, keep it in sync when that changes.
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import or_, select
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
    - Changing a staff member's positions

    The next request from this staff member will re-resolve from the DB
    and repopulate the cache.  Silently no-ops if Redis is not initialised
    (e.g. during tests or seed scripts).
    """
    try:
        await get_redis().delete(f"{_CACHE_KEY_PREFIX}{staff_id}")
    except RuntimeError:
        pass


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

    from app.models.auth import PositionPermission, StaffPermission, StaffPosition
    from app.models.staff import StaffMember, StaffType, staff_member_positions
    from app.models.academic import ClassTeacher
    from app.models.housing import HouseMaster

    perms: dict[str, bool] = {}

    # Layer 2: union permissions from ALL positions the staff member holds.
    # If any position grants a permission, it is granted (additive model).
    staff = await db.get(StaffMember, staff_member_id)
    if staff:
        pos_id_rows = await db.execute(
            select(staff_member_positions.c.position_id).where(
                staff_member_positions.c.staff_member_id == staff_member_id
            )
        )
        directly_assigned_ids = [r[0] for r in pos_id_rows]
        # Scoped to this staff member's own school_id as defense in depth,
        # mirroring Layer 1's override scoping below: the write path
        # (services/staff.py::_assert_positions_owned) already enforces this
        # at assignment time, but a stray or historical cross-school
        # position_id in staff_member_positions would otherwise still be
        # picked up here and directly grant that other school's permission
        # set — the exact leak the fork-on-edit mechanism (12ap) exists to
        # prevent, reached through a different, unguarded door.
        position_ids: list[uuid.UUID] = []
        if directly_assigned_ids:
            position_ids = list(await db.scalars(
                select(StaffPosition.id).where(
                    StaffPosition.id.in_(directly_assigned_ids),
                    or_(StaffPosition.school_id == staff.school_id, StaffPosition.school_id.is_(None)),
                )
            ))

        # Auto-derive TEACHER, CLASS_TEACHER, and HOUSEMASTER positions —
        # none of these three are manually granted. TEACHER is the core
        # role, not an optional responsibility like the other two: it
        # tracks StaffCategory.staff_type == TEACHING (set on every staff
        # member at creation via Employment > Category) rather than a real
        # assignment row, so a teacher never needs to be manually "added" to
        # their own job. CLASS_TEACHER/HOUSEMASTER stay assignment-row-based
        # as before. school_id filtered explicitly for the assignment-row
        # checks, not just implied by staff_member_id being unique to one
        # school: without it, a cross-school ClassTeacher/HouseMaster row
        # planted against this staff member's real id (e.g. via a missing
        # ownership check elsewhere — see academic_teachers.py's
        # assign_class_teacher) would still be picked up here and grant the
        # position's permissions, even though the row belongs to a school
        # this person doesn't work for. TEACHER has no such planting risk —
        # staff.category is read straight off the staff member's own row.
        derived_codes: list[str] = []
        if staff.category and staff.category.staff_type == StaffType.TEACHING:
            derived_codes.append("TEACHER")

        is_ct = await db.scalar(
            select(ClassTeacher.id).where(
                ClassTeacher.staff_member_id == staff_member_id,
                ClassTeacher.school_id == staff.school_id,
                ClassTeacher.is_active == True,  # noqa: E712
            ).limit(1)
        )
        if is_ct:
            derived_codes.append("CLASS_TEACHER")

        is_hm = await db.scalar(
            select(HouseMaster.id).where(
                HouseMaster.staff_member_id == staff_member_id,
                HouseMaster.school_id == staff.school_id,
                HouseMaster.is_active == True,  # noqa: E712
            ).limit(1)
        )
        if is_hm:
            derived_codes.append("HOUSEMASTER")

        if derived_codes:
            # Same "school-specific copy wins over the shared platform
            # template" rule as routers/permissions.py's list endpoint —
            # without the school_id filter, a *different* school forking its
            # own CLASS_TEACHER/HOUSEMASTER copy would leak into every other
            # school's derived staff (code alone isn't unique across
            # schools), and even within one school a fork would only ever
            # add to the template's permissions instead of replacing them.
            derived_rows = await db.execute(
                select(StaffPosition.id, StaffPosition.code, StaffPosition.school_id).where(
                    StaffPosition.code.in_(derived_codes),
                    or_(StaffPosition.school_id == staff.school_id, StaffPosition.school_id.is_(None)),
                )
            )
            by_code: dict[str, uuid.UUID] = {}
            for pid, code, sid in derived_rows:
                if code not in by_code or sid is not None:
                    by_code[code] = pid
            position_ids.extend(by_code.values())

        if position_ids:
            position_rows = await db.execute(
                select(PositionPermission).where(
                    PositionPermission.position_id.in_(position_ids)
                )
            )
            for row in position_rows.scalars():
                key = f"{row.module}.{row.action}"
                # Grant wins: if any position grants it, it's granted
                if row.is_allowed or key not in perms:
                    perms[key] = row.is_allowed

    # Layer 1: apply personal overrides — these always win. Scoped to the
    # staff member's own school_id as defense in depth: the write path
    # (services/staff_permissions.py) already enforces this, but a mismatched
    # school_id here would otherwise still be picked up by staff_member_id
    # alone, letting a stray or historical cross-school row apply.
    if staff:
        override_rows = await db.execute(
            select(StaffPermission).where(
                StaffPermission.staff_member_id == staff_member_id,
                StaffPermission.school_id == staff.school_id,
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


async def user_has_permission(
    user_id: uuid.UUID,
    module: str,
    action: str,
    db: AsyncSession,
) -> bool:
    """
    Same as has_permission(), but starting from a User row instead of a
    staff_member_id — for ad hoc checks inside service functions where the
    caller only has the authenticated user_id (e.g. an override permission
    that differs from the permission the route itself is gated on).

    Superadmin always returns True. A user with no staff_member_id (e.g. a
    portal login) always returns False.
    """
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user:
        return False
    if user.is_superadmin:
        return True
    if not user.staff_member_id:
        return False
    return await has_permission(user.staff_member_id, module, action, db)


async def check_term_lock_override(
    academic_term_id: uuid.UUID,
    requested_reason: str | None,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> str | None:
    """
    Enforce AcademicTerm.results_locked for a mutating action.

    Returns None if the term isn't locked (nothing to record). Otherwise
    returns the stripped override reason, raising 423 if the caller lacks
    assessments.approve_scores or didn't supply one. Shared by
    services/scoring.py (score submit/approve) and services/assessment.py
    (assessment edit) so the lock is enforced identically everywhere.
    """
    from fastapi import HTTPException, status
    from app.models.academic import AcademicTerm

    term = await db.get(AcademicTerm, academic_term_id)
    if not term or not term.results_locked:
        return None
    reason = (requested_reason or "").strip()
    if not reason or not await user_has_permission(user_id, "assessments", "approve_scores", db):
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "This term's results are locked. A user with assessments.approve_scores "
            "can override by supplying an override_reason.",
        )
    return reason
