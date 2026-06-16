"""
Schools router — HTTP endpoints for school management.

This file is intentionally thin.  Its only jobs are:
  1. Declare the HTTP routes.
  2. Enforce access control via dependencies.
  3. Delegate to services/school.py for business logic.

ACCESS CONTROL SUMMARY
----------------------
GET  /schools/regions              Public — no auth required (needed for signup forms)
GET  /schools/districts            Public — no auth required
GET  /schools/public/{subdomain}   Public — branding for the login screen
POST /schools                      Superadmin only (require_superadmin)
GET  /schools                      Any authenticated user
GET  /schools/{id}                 Any authenticated user
PATCH /schools/{id}                Requires 'school.edit' permission
PUT  /schools/{id}/config          Requires 'school.edit' permission
GET  /schools/{id}/config          Any authenticated user
PUT  /schools/{id}/sms-config      Requires 'school.edit' permission
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission, require_superadmin
from app.models.school import GhanaDistrict, GhanaRegion
from app.schemas.school import (
    DistrictRead,
    RegionRead,
    SchoolBranding,
    SchoolByDomainResult,
    SchoolConfigSet,
    SchoolCreate,
    SchoolRead,
    SchoolUpdate,
    SmsConfigCreate,
    SmsConfigRead,
)
from app.services import school as school_svc
from app.services import school_config as config_svc

router = APIRouter(prefix="/schools", tags=["schools"])


# ── Public reference data ─────────────────────────────────────────────────────
# These endpoints are intentionally unauthenticated because they are needed
# on school registration forms before any user account exists.

@router.get("/regions", response_model=list[RegionRead])
async def list_regions(db: AsyncSession = Depends(get_db)):
    """Return all 16 Ghana regions ordered by name."""
    rows = await db.scalars(select(GhanaRegion).order_by(GhanaRegion.name))
    return [RegionRead.model_validate(r) for r in rows]


@router.get("/districts", response_model=list[DistrictRead])
async def list_districts(
    region_id: uuid.UUID | None = Query(None, description="Filter by region"),
    db: AsyncSession = Depends(get_db),
):
    """Return Ghana districts, optionally filtered to a single region."""
    stmt = select(GhanaDistrict).order_by(GhanaDistrict.name)
    if region_id:
        stmt = stmt.where(GhanaDistrict.region_id == region_id)
    rows = await db.scalars(stmt)
    return [DistrictRead.model_validate(d) for d in rows]


# ── Public branding (no auth — called before login) ──────────────────────────

@router.get("/public/{subdomain}", response_model=SchoolBranding)
async def get_school_branding(
    subdomain: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return branding data for a school identified by its subdomain.

    No authentication required — this is called by the frontend before
    the login screen renders so the school's logo, colours, and motto
    can be displayed to the user before they log in.
    """
    return await school_svc.get_school_branding(subdomain, db)


# ── Custom domain resolution (no auth — called before login) ─────────────────

@router.get("/by-domain", response_model=SchoolByDomainResult)
async def get_school_by_custom_domain(
    h: str = Query(..., description="Full hostname, e.g. portal.presec.com"),
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve a custom domain to its school and return branding + routing identifiers.

    No authentication required — called on mount when the browser is on a
    school-owned domain (e.g. portal.presec.com) rather than the platform
    subdomain (presec.ttek-sms.com).
    """
    return await school_svc.get_school_by_custom_domain(h, db)


# ── Authenticated branding (after login, school not yet in localStorage) ───────

@router.get("/my-branding", response_model=SchoolBranding)
async def get_my_school_branding(
    ids: tuple = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return branding data for the currently authenticated user's school."""
    _user_id, school_id = ids
    return await school_svc.get_school_branding_by_id(school_id, db)


@router.get("/me", response_model=SchoolRead)
async def get_my_school(
    ids: tuple = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return full school profile for the authenticated user's school."""
    _user_id, school_id = ids
    return await school_svc.get_school(school_id, db)


@router.patch("/me", response_model=SchoolRead)
async def update_my_school(
    req: SchoolUpdate,
    ids: tuple = Depends(require_permission("school", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's school profile fields."""
    _user_id, school_id = ids
    return await school_svc.update_school(school_id, req, db)


@router.post("/me/logo", response_model=SchoolRead)
async def upload_my_school_logo(
    file: UploadFile,
    ids: tuple = Depends(require_permission("school", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload or replace the school logo.

    Accepts JPEG, PNG, or WebP up to 2 MB.  Stored as WebP, max 400 × 400 px.
    School admins with school.edit permission can manage their own logo.
    """
    _user_id, school_id = ids
    return await school_svc.upload_school_logo(school_id, file, db)


# ── School registration (superadmin only) ─────────────────────────────────────

@router.post("", response_model=SchoolRead, status_code=201)
async def create_school(
    req: SchoolCreate,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new school on the platform.

    Only the platform superadmin can do this.  School headmasters cannot
    self-register — Tagnatek provisions each school.
    """
    return await school_svc.create_school(req, db)


# ── School queries (any authenticated user) ───────────────────────────────────

@router.get("", response_model=list[SchoolRead])
async def list_schools(
    active_only: bool = Query(True, description="Exclude deactivated schools"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _ids: tuple = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """List schools with pagination.  Superadmin sees all; school users see only their own."""
    return await school_svc.list_schools(db, active_only=active_only, limit=limit, offset=offset)


@router.get("/{school_id}", response_model=SchoolRead)
async def get_school(
    school_id: uuid.UUID,
    _ids: tuple = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single school by its UUID."""
    return await school_svc.get_school(school_id, db)


# ── School updates (requires 'school.edit' permission) ───────────────────────

@router.patch("/{school_id}", response_model=SchoolRead)
async def update_school(
    school_id: uuid.UUID,
    req: SchoolUpdate,
    _ids: tuple = Depends(require_permission("school", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Update school profile fields.  school_code and school_type cannot be changed."""
    return await school_svc.update_school(school_id, req, db)


@router.post("/{school_id}/logo", response_model=SchoolRead)
async def upload_logo(
    school_id: uuid.UUID,
    file: UploadFile,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload or replace the school logo.

    Superadmin only — logo is set during school provisioning, not by school admins.
    Accepts JPEG, PNG, or WebP up to 2 MB.  Stored as WebP, max 400 × 400 px.
    """
    return await school_svc.upload_school_logo(school_id, file, db)


@router.put("/{school_id}/config", status_code=204)
async def set_config(
    school_id: uuid.UUID,
    req: SchoolConfigSet,
    _ids: tuple = Depends(require_permission("school", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a single config key-value pair for the school."""
    await config_svc.set_config(school_id, req, db)


@router.get("/{school_id}/config")
async def get_config(
    school_id: uuid.UUID,
    _ids: tuple = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return all config key-value pairs for the school as a JSON object."""
    return await config_svc.get_config(school_id, db)


@router.put("/{school_id}/sms-config", response_model=SmsConfigRead)
async def upsert_sms_config(
    school_id: uuid.UUID,
    req: SmsConfigCreate,
    _ids: tuple = Depends(require_permission("school", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the SMS provider configuration for the school."""
    return await config_svc.upsert_sms_config(school_id, req, db)
