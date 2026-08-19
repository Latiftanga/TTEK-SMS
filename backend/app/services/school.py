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

import re
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.school import GhanaDistrict, GhanaRegion, School
from app.schemas.school import SchoolBranding, SchoolCreate, SchoolRead, SchoolSummary, SchoolUpdate, _logo_url

# Mirrors frontend/src/lib/stores/subdomain.ts's RESERVED set — an
# auto-generated subdomain must never collide with a platform route.
_SUBDOMAIN_RESERVED = {"www", "api", "admin", "mail", "staging", "dev"}


def _slugify_subdomain(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:50].rstrip("-")
    if len(slug) < 3:
        slug = (slug + "-school").strip("-")[:50]
    return slug or "school"


async def _generate_unique_subdomain(name: str, db: AsyncSession) -> str:
    """Every school gets a branded <slug>.ttek-sms.com login page by
    default, with zero admin action required — a school that never touches
    the subdomain field still lands on a fully-branded URL, not a bare
    shared domain. Appends -2, -3, ... on collision (with an existing
    school's subdomain or a reserved word like 'www')."""
    base = _slugify_subdomain(name)
    if base in _SUBDOMAIN_RESERVED:
        base = f"{base}-school"
    candidate, n = base, 2
    while candidate in _SUBDOMAIN_RESERVED or await db.scalar(
        select(School.id).where(School.subdomain == candidate)
    ):
        candidate = f"{base}-{n}"[:50]
        n += 1
    return candidate


# ── School CRUD ───────────────────────────────────────────────────────────────

async def create_school(req: SchoolCreate, db: AsyncSession) -> SchoolRead:
    """
    Register a new school on the platform.

    Validates that the school_code is not already taken and that the
    provided region and district IDs exist in the reference data. A blank
    subdomain is auto-generated from the school name (see
    _generate_unique_subdomain) rather than left null, so every school gets
    a branded login URL by default.

    Raises:
        409  school_code is already registered by another school.
        409  subdomain (if explicitly given) is already taken.
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
        subdomain = req.subdomain
    else:
        subdomain = await _generate_unique_subdomain(req.name, db)

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

    school = School(**{**req.model_dump(), "subdomain": subdomain})
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
    *,
    allow_domain_change: bool = False,
) -> SchoolRead:
    """
    Apply a partial update to a school's profile fields.

    Only fields present in the request body are changed (PATCH semantics).
    school_code and school_type cannot be updated after creation — those
    fields are not included in SchoolUpdate.

    allow_domain_change gates subdomain/custom_domain specifically — a
    school's own sign-in link is how every staff/student bookmark, invite
    email, and (for custom_domain) real DNS/TLS record point at them, so a
    school admin changing it themselves silently breaks all of those with
    no platform-side awareness. Only the superadmin PATCH /schools/{id}
    route passes True; the self-service PATCH /schools/me route (routers/
    schools.py::update_my_school) never does, leaving domain changes as an
    out-of-band request to Tagnatek instead of an in-app self-service field.

    Raises:
        404  School not found.
        403  subdomain/custom_domain present in the request but the caller
             isn't allowed to change them.
    """
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{school_id}' not found.",
        )

    updates = req.model_dump(exclude_unset=True)

    if not allow_domain_change and ("subdomain" in updates or "custom_domain" in updates):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your sign-in link (subdomain/custom domain) can only be changed by "
            "the platform administrator — contact Tagnatek support to update it.",
        )

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
    # updated_at is server-generated (onupdate=func.now()) — without an
    # explicit refresh, SchoolRead.model_validate() reading it straight
    # after flush() can trigger a lazy reload outside an async context,
    # raising MissingGreenlet. refresh() issues a real, awaited SELECT so
    # every attribute (not just updated_at) is guaranteed loaded first.
    await db.refresh(school)
    return SchoolRead.model_validate(school)


async def list_schools(
    db: AsyncSession,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> list[SchoolSummary]:
    """
    Return schools on the platform with pagination, plus per-school usage
    stats — this is the superadmin dashboard's own management view, the
    only caller of this function, so it defaults to showing EVERY school
    including disabled ones (active_only defaults False, unlike every other
    "list" endpoint in this codebase) — a superadmin who just disabled a
    school still needs to find it again to re-enable it later.

    Args:
        active_only: When True, exclude deactivated schools. Default False.
        limit:       Max rows to return (1–500). Prevents OOM on large deployments.
        offset:      Rows to skip — use with limit for cursor-style pagination.
        search:      Case-insensitive partial match against name or school_code.
    """
    from app.models.auth import User
    from app.models.staff import StaffMember
    from app.models.students import Student

    stmt = select(School)
    if active_only:
        stmt = stmt.where(School.is_active.is_(True))
    if search:
        s = f"%{search}%"
        stmt = stmt.where(or_(School.name.ilike(s), School.school_code.ilike(s)))
    stmt = stmt.order_by(School.name).limit(limit).offset(offset)
    schools = list(await db.scalars(stmt))
    if not schools:
        return []

    school_ids = [s.id for s in schools]
    student_counts = dict((await db.execute(
        select(Student.school_id, func.count())
        .where(Student.school_id.in_(school_ids))
        .group_by(Student.school_id)
    )).all())
    staff_counts = dict((await db.execute(
        select(StaffMember.school_id, func.count())
        .where(StaffMember.school_id.in_(school_ids))
        .group_by(StaffMember.school_id)
    )).all())
    last_logins = dict((await db.execute(
        select(User.school_id, func.max(User.last_login_at))
        .where(User.school_id.in_(school_ids))
        .group_by(User.school_id)
    )).all())

    return [
        SchoolSummary(
            **SchoolRead.model_validate(s).model_dump(),
            student_count=student_counts.get(s.id, 0),
            staff_count=staff_counts.get(s.id, 0),
            last_login_at=last_logins.get(s.id),
        )
        for s in schools
    ]


async def delete_school(school_id: uuid.UUID, db: AsyncSession) -> None:
    """
    Permanently delete a school. school_id is ondelete="CASCADE" on every
    school-scoped table (SchoolScopedMixin) — a successful delete here wipes
    every row anywhere in the schema that ever referenced this school, with
    no recovery.

    Deliberately a narrow cleanup tool, never a "remove a real school"
    action — two hard preconditions, neither has an override:
      - already disabled (is_active=False). Deleting a live school is never
        a single action; you must consciously disable it first.
      - genuinely empty: zero students AND zero staff. A school with either
        can never be deleted through this function, full stop — there is
        no "delete anyway". create_school() never auto-creates any staff or
        student rows, so a school that's still empty really has nothing in
        it but the School row itself and (possibly) incidental config/logo
        rows, which cascade away harmlessly.

    Raises:
        404  School not found.
        422  School is still active — disable it first.
        422  School has students and/or staff — not a safe cleanup target.
    """
    from app.models.staff import StaffMember
    from app.models.students import Student

    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School '{school_id}' not found.",
        )
    if school.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This school is still active — disable it before deleting.",
        )

    student_count = await db.scalar(
        select(func.count()).select_from(Student).where(Student.school_id == school_id)
    )
    staff_count = await db.scalar(
        select(func.count()).select_from(StaffMember).where(StaffMember.school_id == school_id)
    )
    if student_count or staff_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"This school has {student_count} student(s) and {staff_count} staff "
                "member(s) — only a genuinely empty school can be deleted."
            ),
        )

    await db.delete(school)
    await db.flush()


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
    # save_logo() always writes to the same "logos/{school_id}.webp" path —
    # re-uploading a replacement logo assigns logo_path to the exact string
    # it already held. SQLAlchemy's dirty-checker treats a same-value
    # reassignment as no change at all and silently skips the UPDATE
    # entirely (confirmed: no SQL is emitted without this), which also means
    # onupdate=func.now() never fires — updated_at stays stale, the ?v=
    # cache-buster on logo_url never advances, and a browser never re-fetches
    # the new (different) image bytes on disk. flag_modified() forces the
    # UPDATE regardless of the Python-level string being unchanged.
    flag_modified(school, "logo_path")
    await db.flush()
    # See update_school()'s matching comment — updated_at is server-generated
    # and needs an explicit, awaited refresh before synchronous validation.
    await db.refresh(school)
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
        logo_url=_logo_url(school.logo_path, school.updated_at),
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
        404  No active school is registered for this custom domain. Detail is
             deliberately generic ("Not found.") rather than naming "school"
             or echoing the domain back — this endpoint is unauthenticated
             and hit before any login, so its raw response (visible to
             anyone who opens devtools' network tab, not just what the
             frontend chooses to render) must not confirm a per-tenant
             domain-lookup system exists at all. Every school is meant to
             feel like the platform was built for them alone; a distinctive
             "no such school" error is exactly the kind of leak that gives
             the game away to a technically curious visitor.
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
            detail="Not found.",
        )
    return SchoolByDomainResult(
        school_name=school.name,
        short_name=school.short_name,
        school_type=school.school_type,
        motto=school.motto,
        logo_url=_logo_url(school.logo_path, school.updated_at),
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
        404  No active school is registered under this subdomain. Same
             deliberately generic "Not found." detail as get_school_by_
             custom_domain's own 404, for the same reason — see that
             function's docstring.
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
            detail="Not found.",
        )
    return SchoolBranding(
        school_name=school.name,
        short_name=school.short_name,
        school_type=school.school_type,
        motto=school.motto,
        logo_url=_logo_url(school.logo_path, school.updated_at),
        brand_color=school.brand_color,
        school_code=school.school_code,
    )


