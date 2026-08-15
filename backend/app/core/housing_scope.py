"""
Per-house scoping for Housing — mirrors core/student_scope.py's and
core/teacher_scope.py's "resolve caller's scope as a set, then membership
check, 404 not 403" pattern.

BYPASS RULE — deliberately different from Students
----------------------------------------------------
Students (core/student_scope.py) never falls back to full access: a teacher
with zero recorded ClassTeacher/SubjectTeacher rows sees zero students,
never everything, on the theory that "no assignment yet" must never look
like "unrestricted."

Housing inverts that on purpose, per the user's own framing when this module
was built: "admin manages houses, housemasters see only their own house."
HouseMaster is an appointment a school makes only for actual housemasters —
HEAD/DEPUTY_HEAD/BURSAR/ASSISTANT_HEAD_BOARDING never hold one, so "zero
active HouseMaster rows this year" reliably means "this caller isn't a
housemaster at all," not "a housemaster whose assignment got lost." This was
already the de facto behaviour of two hand-rolled checks that existed before
this module (services/housing.py::list_my_houses,
services/housing_events.py::create_exeat) — formalized here and now applied
consistently across every housing endpoint instead of just those two.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.housing import HouseMaster


async def _staff_member_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user or user.is_superadmin:
        return None
    return user.staff_member_id


async def resolve_house_scope(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    academic_year_id: uuid.UUID | None,
    db: AsyncSession,
) -> set[uuid.UUID] | None:
    """None = unrestricted (superadmin, non-staff login, or zero active
    HouseMaster rows this year — see BYPASS RULE above). Empty set = deny
    (zero houses) — this is the `academic_year_id is None` case only (no
    current academic year exists for this school, so "is this caller a
    housemaster" can't even be resolved). SECURITY: fail closed here
    instead of granting unrestricted access, since "no current year" is a
    broken/incomplete setup state, not a green light for every staff
    member to see every house. Checked after the superadmin/non-staff
    bypass so that bypass is never affected by year state."""
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return None
    if academic_year_id is None:
        return set()
    rows = await db.scalars(
        select(HouseMaster.house_id).where(
            HouseMaster.staff_member_id == staff_id,
            HouseMaster.academic_year_id == academic_year_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )
    ids = set(rows)
    return ids or None


async def assert_house_in_scope(
    house_id: uuid.UUID,
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    academic_year_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    """404 (not 403) if the caller manages houses but this one isn't
    theirs — same "don't reveal existence" convention as student_scope.py."""
    scope = await resolve_house_scope(user_id, school_id, academic_year_id, db)
    if scope is not None and house_id not in scope:
        raise HTTPException(404, "House not found.")


async def assert_unrestricted(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    academic_year_id: uuid.UUID | None,
    db: AsyncSession,
    detail: str,
) -> None:
    """For the handful of housing actions that are administrative appointments
    rather than day-to-day house management — creating a new house, deciding
    who a house's HouseMaster is — even a scoped caller's own `housing.manage`
    permission isn't enough; 403 if they resolve to an actual house scope at
    all (a real housemaster), not just "isn't this specific house."""
    if await resolve_house_scope(user_id, school_id, academic_year_id, db) is not None:
        raise HTTPException(403, detail)


async def current_year_id(school_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    """Most housing endpoints (house/room CRUD, roll calls, exeats) have no
    natural year context of their own — House/Room are permanent structures,
    not per-year rows — so "which house(s) do I currently manage" resolves
    against whichever academic year is presently current. Returns None if
    no year is set up yet — resolve_house_scope treats that as deny (empty
    scope), not unrestricted; see its own docstring."""
    from app.services.academic_year import get_current_year

    year = await get_current_year(school_id, db)
    return year.id if year else None
