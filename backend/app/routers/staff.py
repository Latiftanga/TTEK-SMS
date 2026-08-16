"""Staff router — core profile CRUD, import, invite, and password reset.

HR sub-records (contacts, qualifications, promotions, leave, responsibilities)
live in routers/staff_records.py; exports and personal permission overrides
live in routers/staff_admin.py — both split out to stay under the 300-line cap.

ACCESS CONTROL
--------------
GET  /staff, /staff/{id}               staff.view
POST /staff                            staff.create
PATCH /staff/{id}                      staff.edit (profile fields);
                                        position_ids specifically also
                                        requires school.manage_users — see
                                        update_staff's own comment for why
POST /staff/{id}/invite                school.manage_users
POST /staff/{id}/reset-password        school.manage_users

school.manage_users is deliberately the stronger gate for both position
changes and password resets: staff.edit can be held by more than just HEAD
(a personal permission override can grant it to anyone), and neither
position-assignment nor password-reset should be reachable by a staff.edit
holder acting on themselves or a more senior colleague — the first is a direct
self-escalation path (PATCH your own position_ids onto HEAD), the second
is a direct account takeover (reset the HEAD's password, log in as them).
Both actions are logged to AuditLog, which nothing in this module wrote to
before.
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import assert_self_or_permission, require_auth, require_permission
from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.auth import InvitationCreate
from app.schemas.documents import ImportBatchResult
from app.schemas.staff import (
    StaffMemberCreate,
    StaffMemberDetail,
    StaffMemberSummary,
    StaffMemberUpdate,
    TempPasswordResult,
)
from app.services import auth_invite as invite_svc
from app.services import staff as staff_svc
from app.services import staff_import as import_svc
from app.services.staff_import_template import build_template

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post("", response_model=StaffMemberDetail, status_code=201)
async def create_staff(
    req: StaffMemberCreate,
    ids=Depends(require_permission("staff", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await staff_svc.create_staff(req, school_id, db)


@router.get("", response_model=list[StaffMemberSummary])
async def list_staff(
    response: Response,
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    gender: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    items, total = await staff_svc.list_staff(
        school_id, db, active_only=active_only, skip=skip, limit=limit,
        search=search, gender=gender, category_id=category_id,
    )
    response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/import/template")
async def download_import_template(
    ids=Depends(require_permission("staff", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Return a branded .xlsx template pre-loaded with categories as a dropdown."""
    from app.models.school import School, SchoolOwnership
    from app.models.staff import StaffCategory
    from sqlalchemy import or_, select

    _, school_id = ids
    school = await db.get(School, school_id)
    is_public = school and school.ownership == SchoolOwnership.PUBLIC
    condition = (
        or_(StaffCategory.school_id == school_id, StaffCategory.school_id.is_(None))
        if is_public else
        StaffCategory.school_id == school_id
    )
    cat_rows = await db.scalars(
        select(StaffCategory).where(condition, StaffCategory.is_active == True).order_by(StaffCategory.name)
    )
    job_class_names = [c.name for c in cat_rows]
    xlsx_bytes = build_template(
        school_name=school.name if school else "School",
        school_code=school.school_code if school else "SCHOOL",
        brand_color=school.brand_color if school else "#1e40af",
        job_class_names=job_class_names,
    )
    filename = f"staff_import_{school.school_code if school else 'template'}.xlsx"
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportBatchResult, status_code=200)
async def bulk_import_staff(
    file: UploadFile = File(...),
    ids=Depends(require_permission("staff", "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a staff import .xlsx (must be the official template).
    Best-effort: valid rows are created, failed rows are reported with reasons.
    """
    if not file.filename or not file.filename.endswith(".xlsx"):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Only .xlsx files are accepted.")
    user_id, school_id = ids
    from app.models.school import School
    school = await db.get(School, school_id)
    school_code = school.school_code if school else "SCHOOL"
    file_bytes = await file.read()
    return await import_svc.process_import(file_bytes, school_id, school_code, user_id, db)


@router.post("/{staff_id}/reset-password", response_model=TempPasswordResult)
async def reset_staff_password(
    staff_id: uuid.UUID,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Admin resets a staff member's login password and returns a temporary password."""
    import secrets, string
    from datetime import datetime, timezone
    from app.models.auth import AuditLog, User
    from app.core.auth import hash_password
    from sqlalchemy import select

    from app.models.staff import StaffMember

    user_id, school_id = ids
    user = await db.scalar(
        select(User).where(User.staff_member_id == staff_id, User.school_id == school_id)
    )
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No login account found for this staff member.")

    staff = await db.get(StaffMember, staff_id)

    words = ["Blue","Stone","River","Eagle","Cedar","Pearl","Storm","Flame","Coral","Frost"]
    word1 = secrets.choice(words)
    word2 = secrets.choice([w for w in words if w != word1])
    digits = ''.join(secrets.choice(string.digits) for _ in range(3))
    temp = f"{word1}{word2}{digits}"

    user.password_hash = hash_password(temp)
    # Never log the temp password itself — the point of the audit trail is
    # "who reset whose password, when," not a secret-leaking transcript.
    db.add(AuditLog(
        school_id=school_id, user_id=user_id, action="STAFF_PASSWORD_RESET",
        entity_type="StaffMember", entity_id=staff_id,
        new_values={"reset_by_user_id": str(user_id)},
        created_at=datetime.now(timezone.utc),
    ))
    await db.flush()

    display = f"{staff.first_name} {staff.last_name}" if staff else str(staff_id)
    return TempPasswordResult(temporary_password=temp, display_name=display)


@router.get("/{staff_id}", response_model=StaffMemberDetail)
async def get_staff(
    staff_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "view", db)
    return await staff_svc.get_staff(staff_id, school_id, db)


@router.patch("/{staff_id}", response_model=StaffMemberDetail)
async def update_staff(
    staff_id: uuid.UUID,
    req: StaffMemberUpdate,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)

    # Self-edit without staff.edit permission: restrict to personal-contact fields only.
    # Superadmins and staff with staff.edit may update any field.
    from app.models.auth import User
    from app.core.permissions import resolve_permissions, user_has_permission
    caller = await db.get(User, user_id)
    is_self = caller and caller.staff_member_id == staff_id
    has_edit = caller and caller.is_superadmin or (
        caller and caller.staff_member_id and
        (await resolve_permissions(caller.staff_member_id, db)).get("staff.edit", False)
    )
    if is_self and not has_edit:
        req = StaffMemberUpdate(
            phone=req.phone,
            email=req.email,
            address=req.address,
            marital_status=req.marital_status,
        )

    # position_ids is a stronger action than the rest of this endpoint —
    # staff.edit alone (which can be held by more than just HEAD, via a
    # personal permission override) previously let a caller grant themselves
    # or anyone else a more powerful position with no check at all. Gated the same as
    # POST /staff/{id}/invite, the other "decide who has system access"
    # action in this router.
    if req.position_ids is not None and not await user_has_permission(user_id, "school", "manage_users", db):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Changing a staff member's positions requires school.manage_users.",
        )

    return await staff_svc.update_staff(staff_id, req, school_id, db, changed_by_id=user_id)


@router.post("/{staff_id}/invite", status_code=201)
async def invite_staff_to_platform(
    staff_id: uuid.UUID,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Send a platform invitation to an existing staff member using their profile email/phone."""
    from app.models.staff import StaffMember
    from app.models.school import School
    from app.models.auth import User
    from app.services.sms_notifications import notify_staff_invite
    from app.core.config import settings
    from sqlalchemy import select

    user_id, school_id = ids
    member = await db.scalar(
        select(StaffMember).where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
    )
    if not member:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Staff member not found.")
    if not member.email and not member.phone:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Staff member has no email or phone on file.")

    existing_user = await db.scalar(
        select(User).where(User.staff_member_id == staff_id)
    )
    if existing_user:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=409,
            detail="This staff member already has an account. They can sign in directly.",
        )

    invite_req = InvitationCreate(
        email=member.email,
        phone=member.phone,
        staff_member_id=staff_id,
    )
    token = await invite_svc.create_invitation(invite_req, school_id=school_id, invited_by_id=user_id, db=db)

    invite_link = f"{settings.frontend_base_url}/accept-invite?token={token}"
    sms_sent = False
    if member.phone:
        school = await db.get(School, school_id)
        staff_name = member.first_name
        school_name = school.name if school else "your school"
        sms_sent = await notify_staff_invite(
            phone=member.phone,
            staff_name=staff_name,
            school_name=school_name,
            school_id=school_id,
            invite_link=invite_link,
            invitation_id=invite_req.staff_member_id or staff_id,
            db=db,
        )

    return {"invitation_token": token, "invite_link": invite_link, "sms_sent": sms_sent}
