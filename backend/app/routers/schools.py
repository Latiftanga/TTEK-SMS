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
GET  /schools/my-branding          Authenticated — returns branding for caller's school
GET  /schools/me                   Authenticated — full school profile for caller's school
GET  /schools/me/positions         Authenticated — list positions for caller's school
PATCH /schools/me                  Requires 'school.edit' permission (subdomain/custom_domain rejected — superadmin only, see PATCH /schools/{id})
POST /schools/me/logo              Requires 'school.edit' permission
POST /schools                      Superadmin only (require_superadmin)
GET  /schools                      Superadmin only — lists every school platform-wide
GET  /schools/{id}                 Superadmin only (legacy — use /me for self-service)
PATCH /schools/{id}                Superadmin only (legacy — use /me for self-service)
DELETE /schools/{id}               Superadmin only — narrow cleanup tool, see services/school.py::delete_school
POST /schools/{id}/logo            Superadmin only
PUT  /schools/{id}/config          Superadmin only (legacy — use /me self-service where it exists)
GET  /schools/{id}/config          Superadmin only
PUT  /schools/{id}/sms-config      Superadmin only

NOTE: the {id}-path endpoints above used to be gated by require_auth /
require_permission("school", "edit") — that only checks the CALLER's own
permission/school, never that the path {id} matches the caller's own
school_id, so any staff member holding school.edit at their own school
could read/edit ANY other school's profile, config, or SMS credentials by
substituting a different UUID in the path. Since the frontend only ever
calls the /me equivalents (confirmed: no {id}-path call site exists), these
are now superadmin-only — the same fix already applied to POST {id}/logo.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission, require_superadmin
from app.models.auth import StaffPosition
from app.models.school import GhanaDistrict, GhanaRegion
from app.schemas.staff import PositionRead
from app.schemas.school import (
    DistrictRead,
    RegionRead,
    SchoolBranding,
    SchoolByDomainResult,
    SchoolConfigSet,
    SchoolCreate,
    SchoolRead,
    SchoolSummary,
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


@router.get("/me/positions", response_model=list[PositionRead])
async def list_my_positions(
    ids: tuple = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return all staff positions available to the authenticated user's school.

    School-specific positions take precedence over platform templates with the same code.
    """
    from sqlalchemy import or_
    _, school_id = ids
    rows = await db.scalars(
        select(StaffPosition)
        .where(or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)))
        .order_by(StaffPosition.name)
    )
    # TEACHER, CLASS_TEACHER, and HOUSEMASTER are all derived (see
    # core/permissions.py::resolve_permissions), not manually granted —
    # exclude them from the manual "Authority" picker. TEACHER specifically
    # is the core role, not an optional responsibility like the other two.
    DERIVED_CODES = {"TEACHER", "CLASS_TEACHER", "HOUSEMASTER"}
    seen: dict[str, StaffPosition] = {}
    for pos in rows:
        if pos.code in DERIVED_CODES:
            continue
        if pos.code not in seen or pos.school_id is not None:
            seen[pos.code] = pos
    return sorted(seen.values(), key=lambda p: p.name)


@router.patch("/me", response_model=SchoolRead)
async def update_my_school(
    req: SchoolUpdate,
    ids: tuple = Depends(require_permission("school", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's school profile fields. subdomain/
    custom_domain are rejected here (403) even if included in the request —
    only the superadmin route can change a school's sign-in link."""
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

@router.get("", response_model=list[SchoolSummary])
async def list_schools(
    active_only: bool = Query(False, description="Exclude deactivated schools"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    search: str | None = Query(None, description="Partial match against name or school_code"),
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """List every school on the platform, paginated, with usage stats.
    Superadmin only — a school's own users already have everything they
    need via /schools/me. Defaults to showing disabled schools too (unlike
    every other list endpoint's active_only default) since this is the
    superadmin's own management view — they need to find a disabled school
    to re-enable it, not just the ones currently in use."""
    return await school_svc.list_schools(
        db, active_only=active_only, limit=limit, offset=offset, search=search
    )


@router.get("/{school_id}", response_model=SchoolRead)
async def get_school(
    school_id: uuid.UUID,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single school by its UUID. Superadmin only — use /schools/me
    for the caller's own school."""
    return await school_svc.get_school(school_id, db)


# ── School updates (superadmin only — see module docstring) ──────────────────

@router.patch("/{school_id}", response_model=SchoolRead)
async def update_school(
    school_id: uuid.UUID,
    req: SchoolUpdate,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update school profile fields.  school_code and school_type cannot be changed.
    Only this superadmin-only route may change subdomain/custom_domain — see
    services/school.py::update_school's own docstring for why."""
    return await school_svc.update_school(school_id, req, db, allow_domain_change=True)


@router.delete("/{school_id}", status_code=204)
async def delete_school(
    school_id: uuid.UUID,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a school — only ever safe for an already-disabled,
    genuinely empty one (zero students, zero staff). See services/school.py
    ::delete_school's own docstring for the full precondition list; there is
    no override for either check, from any caller."""
    await school_svc.delete_school(school_id, db)


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
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a single config key-value pair for the school."""
    await config_svc.set_config(school_id, req, db)


@router.get("/{school_id}/config")
async def get_config(
    school_id: uuid.UUID,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return all config key-value pairs for the school as a JSON object."""
    return await config_svc.get_config(school_id, db)


@router.put("/{school_id}/sms-config", response_model=SmsConfigRead)
async def upsert_sms_config(
    school_id: uuid.UUID,
    req: SmsConfigCreate,
    _ids: tuple = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the SMS provider configuration for the school."""
    return await config_svc.upsert_sms_config(school_id, req, db)
