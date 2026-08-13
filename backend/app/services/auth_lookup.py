"""
User lookup helpers for multi-tenant identity resolution.

Separated from services/auth.py so both auth.py and auth_reset.py can
import these without circular dependencies.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import LoginType, User
from app.models.school import School
from app.schemas.auth import LoginRequest


async def resolve_school_id(school_code: str, db: AsyncSession) -> uuid.UUID | None:
    """
    Resolve any school identifier string to a school_id.

    Accepts any of the three forms the frontend may send:
      - school_code   e.g. "PRESEC-GH"           matched case-insensitively
      - subdomain     e.g. "presec"               matched lowercase
      - custom_domain e.g. "portal.willigif.com"  matched lowercase

    On subdomain deployments the frontend sends the subdomain. On custom-domain
    deployments the frontend resolves the domain to a school_code via
    GET /schools/by-domain on mount, then sends that school_code.

    A deactivated school (School.is_active=False) never resolves — this is
    what makes "Deactivate" in the superadmin console an actual access
    block, not just a cosmetic flag hidden from list_schools/branding
    lookups: every login/forgot-password/verify-otp call funnels through
    find_user_by_identifier -> here, so no school_code/subdomain/custom_domain
    for a deactivated school can ever resolve a school_id, and the caller
    (find_user_by_identifier) already 404s "School not found" for that case.

    Returns None if no school matches (caller decides whether that is an error).
    """
    slug = school_code.strip().lower()
    school = await db.scalar(
        select(School).where(
            or_(
                func.lower(School.school_code) == slug,
                School.subdomain == slug,
                School.custom_domain == slug,
            ),
            School.is_active.is_(True),
        )
    )
    return school.id if school else None


async def find_user_by_identifier(req: LoginRequest, db: AsyncSession) -> User | None:
    """
    Locate a user by the appropriate identifier, always scoped to a school.

    school_code is required on every LoginRequest (schema-enforced — see
    schemas/auth.py) and resolved once here; every login_type is then
    looked up scoped to that school uniformly. There is no unscoped/global
    lookup in this function at all — every school is reached only via its
    own subdomain/custom domain, which resolves school_code automatically
    before the request is ever sent (login/+page.svelte), so a caller here
    always has one. Platform-admin login is a fully separate function
    (services/auth.py::superadmin_login) that never calls this at all —
    every query below explicitly excludes is_superadmin accounts too, so
    the exclusion holds regardless of whether a given superadmin row
    happens to carry a school_id (the real one never does, but this
    shouldn't depend on that as an implicit assumption).

    Returns None if no matching user exists (caller decides what error to raise).

    Raises:
        404  school_code does not resolve to any school.
    """
    school_id = await resolve_school_id(req.school_code, db)
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{req.school_code}' not found.",
        )

    if req.login_type == LoginType.EMAIL:
        return await db.scalar(
            select(User).where(
                User.email == req.identifier.lower().strip(),
                User.school_id == school_id,
                User.is_superadmin.is_(False),
            )
        )

    if req.login_type == LoginType.PHONE:
        return await db.scalar(
            select(User).where(
                User.phone == req.identifier.strip(),
                User.school_id == school_id,
                User.is_superadmin.is_(False),
            )
        )

    # ADMISSION_ID
    return await db.scalar(
        select(User).where(
            User.school_id == school_id,
            User.admission_id == req.identifier.strip(),
            User.login_type == LoginType.ADMISSION_ID,
        )
    )
