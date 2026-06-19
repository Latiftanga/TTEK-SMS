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

    Returns None if no school matches (caller decides whether that is an error).
    """
    slug = school_code.strip().lower()
    school = await db.scalar(
        select(School).where(
            or_(
                func.lower(School.school_code) == slug,
                School.subdomain == slug,
                School.custom_domain == slug,
            )
        )
    )
    return school.id if school else None


async def find_user_by_identifier(req: LoginRequest, db: AsyncSession) -> User | None:
    """
    Locate a user by the appropriate identifier, scoped to a school when known.

    Multi-tenant scoping rules:
      - school_code provided → resolve school_id, then filter User.school_id.
        This is always the case for requests originating from a school subdomain
        or custom domain — both frontends send school_code in every request.
      - school_code absent   → global lookup (superadmin / platform-admin login
        from the root domain where no school context exists).
      - ADMISSION_ID login   → school_code is always required because the same
        admission number can exist in two different schools.

    Returns None if no matching user exists (caller decides what error to raise).
    """
    school_id: uuid.UUID | None = None
    if req.school_code:
        school_id = await resolve_school_id(req.school_code, db)

    if req.login_type == LoginType.EMAIL:
        q = select(User).where(User.email == req.identifier.lower().strip())
        if school_id:
            q = q.where(User.school_id == school_id)
        return await db.scalar(q)

    if req.login_type == LoginType.PHONE:
        q = select(User).where(User.phone == req.identifier.strip())
        if school_id:
            q = q.where(User.school_id == school_id)
        return await db.scalar(q)

    # ADMISSION_ID: school_code is mandatory.
    if not req.school_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="school_code is required when login_type is ADMISSION_ID.",
        )
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{req.school_code}' not found.",
        )
    return await db.scalar(
        select(User).where(
            User.school_id == school_id,
            User.admission_id == req.identifier.strip(),
            User.login_type == LoginType.ADMISSION_ID,
        )
    )
