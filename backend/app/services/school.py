"""
School management service — registration, configuration, and SMS setup.

This service handles all mutations and queries related to School records.
It enforces business rules that do not belong in the HTTP layer (routers)
or the database layer (models).

SCHOOL CREATION RULES
---------------------
- Only the platform superadmin can register new schools.
  This is enforced by the require_superadmin dependency in the router,
  NOT in this service.  The service trusts that the router has already
  checked authorization before calling it.

- A school_code must be globally unique.  It is the GES-assigned identifier
  and is used as the lookup key for ADMISSION_ID logins
  (see services/auth.py → _find_user_by_identifier).

- region_id and district_id must reference rows that exist in the seeded
  GhanaRegion and GhanaDistrict tables.

SCHOOL CONFIG
-------------
SchoolConfig is a simple key-value store for per-school settings.
Each (school_id, key) pair is unique — set_config() is an upsert.
Example keys: "academic_year_format", "report_card_template", "timezone".

SMS CONFIG
----------
SmsConfig holds provider credentials per school (API key, sender ID).
One row per provider per school.  upsert_sms_config() creates or updates.
Only one provider should have is_active=True at a time; the application
reads the active config when sending SMS (future SmsService driver).
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import GhanaDistrict, GhanaRegion, School
from app.schemas.school import SchoolBranding, SchoolCreate, SchoolRead, SchoolUpdate, _logo_url


# ── School CRUD ───────────────────────────────────────────────────────────────

async def create_school(req: SchoolCreate, db: AsyncSession) -> SchoolRead:
    """
    Register a new school on the platform.

    Validates that the school_code is not already taken and that the
    provided region and district IDs exist in the reference data.

    Raises:
        409  school_code is already registered by another school.
        404  region_id or district_id not found in reference data.
    """
    existing = await db.scalar(
        select(School).where(School.school_code == req.school_code)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"School code '{req.school_code}' is already registered.",
        )

    if req.subdomain:
        taken = await db.scalar(
            select(School).where(School.subdomain == req.subdomain)
        )
        if taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{req.subdomain}' is already taken.",
            )

    region = await db.get(GhanaRegion, req.region_id)
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region ID '{req.region_id}' not found in reference data.",
        )

    district = await db.get(GhanaDistrict, req.district_id)
    if not district:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District ID '{req.district_id}' not found in reference data.",
        )

    school = School(**req.model_dump())
    db.add(school)
    await db.flush()
    return SchoolRead.model_validate(school)


async def get_school(school_id: uuid.UUID, db: AsyncSession) -> SchoolRead:
    """
    Fetch a single school by its primary key.

    Raises:
        404  School not found.
    """
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{school_id}' not found.",
        )
    return SchoolRead.model_validate(school)


async def get_school_by_code(school_code: str, db: AsyncSession) -> SchoolRead:
    """
    Fetch a school by its GES school code (case-insensitive).

    Raises:
        404  No school with this code exists.
    """
    school = await db.scalar(
        select(School).where(School.school_code == school_code.upper())
    )
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School with code '{school_code.upper()}' not found.",
        )
    return SchoolRead.model_validate(school)


async def update_school(
    school_id: uuid.UUID,
    req: SchoolUpdate,
    db: AsyncSession,
) -> SchoolRead:
    """
    Apply a partial update to a school's profile fields.

    Only fields present in the request body are changed (PATCH semantics).
    school_code and school_type cannot be updated after creation — those
    fields are not included in SchoolUpdate.

    Raises:
        404  School not found.
    """
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{school_id}' not found.",
        )

    updates = req.model_dump(exclude_unset=True)

    if "subdomain" in updates and updates["subdomain"]:
        taken = await db.scalar(
            select(School).where(
                School.subdomain == updates["subdomain"],
                School.id != school_id,
            )
        )
        if taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{updates['subdomain']}' is already taken.",
            )

    for field, value in updates.items():
        setattr(school, field, value)

    await db.flush()
    return SchoolRead.model_validate(school)


async def list_schools(
    db: AsyncSession,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[SchoolRead]:
    """
    Return schools on the platform with pagination.

    Args:
        active_only: When True (default), exclude deactivated schools.
        limit:       Max rows to return (1–500). Prevents OOM on large deployments.
        offset:      Rows to skip — use with limit for cursor-style pagination.
    """
    stmt = select(School)
    if active_only:
        stmt = stmt.where(School.is_active.is_(True))
    stmt = stmt.order_by(School.name).limit(limit).offset(offset)
    rows = await db.scalars(stmt)
    return [SchoolRead.model_validate(s) for s in rows]


# ── Logo upload ──────────────────────────────────────────────────────────────

async def upload_school_logo(
    school_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession,
) -> SchoolRead:
    """
    Save a new logo for the school and update logo_path.

    Delegates file validation and storage to services/storage.py.
    Returns the updated school record.

    Raises:
        404  School not found.
        415  File is not JPEG, PNG, or WebP.
        413  File exceeds 2 MB.
        422  File content is not a valid image.
    """
    from app.services.storage import save_logo

    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{school_id}' not found.",
        )

    school.logo_path = await save_logo(file, school_id)
    await db.flush()
    return SchoolRead.model_validate(school)


# ── Public branding ───────────────────────────────────────────────────────────

async def get_school_branding_by_id(school_id: uuid.UUID, db: AsyncSession) -> SchoolBranding:
    """Return branding data for an authenticated user's own school."""
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found.",
        )
    return SchoolBranding(
        school_name=school.name,
        short_name=school.short_name,
        school_type=school.school_type,
        motto=school.motto,
        logo_url=_logo_url(school.logo_path),
        brand_color=school.brand_color,
        school_code=school.school_code,
    )


async def get_school_by_custom_domain(domain: str, db: AsyncSession) -> "SchoolByDomainResult":
    """
    Resolve a custom domain to its school and return branding + routing info.

    Called before login when the browser is on a school-owned domain
    (e.g. portal.presec.com) rather than the platform subdomain.
    No authentication required.

    Raises:
        404  No active school is registered for this custom domain.
    """
    from app.schemas.school import SchoolByDomainResult  # local import avoids circular
    school = await db.scalar(
        select(School).where(
            School.custom_domain == domain.lower().strip(),
            School.is_active.is_(True),
        )
    )
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No school is registered for the domain '{domain}'.",
        )
    return SchoolByDomainResult(
        school_name=school.name,
        short_name=school.short_name,
        school_type=school.school_type,
        motto=school.motto,
        logo_url=_logo_url(school.logo_path),
        brand_color=school.brand_color,
        school_code=school.school_code,
        subdomain=school.subdomain,
    )


async def get_school_branding(subdomain: str, db: AsyncSession) -> SchoolBranding:
    """
    Return public branding data for the given subdomain.

    Called before login — no authentication required.
    Only exposes data safe for public consumption.

    Raises:
        404  No active school is registered under this subdomain.
    """
    school = await db.scalar(
        select(School).where(
            School.subdomain == subdomain.lower(),
            School.is_active.is_(True),
        )
    )
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No school found at '{subdomain}'.",
        )
    return SchoolBranding(
        school_name=school.name,
        short_name=school.short_name,
        school_type=school.school_type,
        motto=school.motto,
        logo_url=_logo_url(school.logo_path),
        brand_color=school.brand_color,
        school_code=school.school_code,
    )


