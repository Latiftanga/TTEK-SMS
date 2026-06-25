"""Staff router — profiles, contacts, qualifications, promotions, and leave.

ACCESS CONTROL
--------------
GET  /staff, /staff/{id}               staff.view
POST /staff                            staff.create
PATCH /staff/{id}                      staff.edit
POST /staff/{id}/invite                school.manage_users
POST/PATCH/DELETE contacts & qualifications  staff.edit
POST/PATCH/DELETE /staff/{id}/promotions     staff.edit
GET  /staff/{id}/promotions                  staff.view
POST /staff/{id}/leave                 staff.edit
GET  /staff/{id}/leave                 staff.view
GET  /staff/leave/pending              staff.approve_leave
PATCH /staff/leave/{id}/review         staff.approve_leave
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import assert_self_or_permission, require_auth, require_permission
from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.auth import InvitationCreate
from app.schemas.documents import ImportBatchResult
from app.schemas.staff import (
    EmergencyContactCreate,
    EmergencyContactRead,
    LeaveCreate,
    LeaveRead,
    LeaveReview,
    PromotionCreate,
    PromotionRead,
    PromotionUpdate,
    QualificationCreate,
    QualificationRead,
    QualificationUpdate,
    StaffMemberCreate,
    StaffMemberDetail,
    StaffMemberSummary,
    StaffMemberUpdate,
    StaffResponsibilities,
    TempPasswordResult,
)
from app.services import auth_invite as invite_svc
from app.services import staff as staff_svc
from app.services import staff_contacts as contacts_svc
from app.services import staff_import as import_svc
from app.services import staff_leave as leave_svc
from app.services import staff_responsibilities as responsibilities_svc
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
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await staff_svc.list_staff(school_id, db, active_only=active_only, skip=skip, limit=limit)


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
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Admin resets a staff member's login password and returns a temporary password."""
    import secrets, string
    from app.models.auth import User
    from app.core.auth import hash_password
    from sqlalchemy import select

    from app.models.staff import StaffMember

    _, school_id = ids
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
    await db.flush()

    display = f"{staff.first_name} {staff.last_name}" if staff else str(staff_id)
    return TempPasswordResult(temporary_password=temp, display_name=display)


@router.get("/leave/pending", response_model=list[LeaveRead])
async def list_pending_leave(
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    leaves = await leave_svc.list_pending_leave(school_id, db)
    return [LeaveRead.model_validate(l) for l in leaves]


@router.patch("/leave/{leave_id}/review", response_model=LeaveRead)
async def review_leave(
    leave_id: uuid.UUID,
    req: LeaveReview,
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    leave = await leave_svc.review_leave(leave_id, req, school_id, db, reviewed_by_id=user_id)
    return LeaveRead.model_validate(leave)


@router.get("/{staff_id}/responsibilities", response_model=StaffResponsibilities)
async def get_staff_responsibilities(
    staff_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "view", db)
    return await responsibilities_svc.get_responsibilities(staff_id, school_id, db)


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
    from app.core.permissions import resolve_permissions
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

    return await staff_svc.update_staff(staff_id, req, school_id, db)


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


@router.post("/{staff_id}/emergency-contacts", response_model=EmergencyContactRead, status_code=201)
async def add_emergency_contact(
    staff_id: uuid.UUID,
    req: EmergencyContactCreate,
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    contact = await contacts_svc.add_emergency_contact(staff_id, req, school_id, db)
    return EmergencyContactRead.model_validate(contact)


@router.delete("/{staff_id}/emergency-contacts/{contact_id}", status_code=204)
async def delete_emergency_contact(
    staff_id: uuid.UUID,
    contact_id: uuid.UUID,
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await contacts_svc.delete_emergency_contact(staff_id, contact_id, school_id, db)


@router.post("/{staff_id}/qualifications", response_model=QualificationRead, status_code=201)
async def add_qualification(
    staff_id: uuid.UUID,
    req: QualificationCreate,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)
    qual = await contacts_svc.add_qualification(staff_id, req, school_id, db)
    return QualificationRead.model_validate(qual)


@router.patch("/{staff_id}/qualifications/{qual_id}", response_model=QualificationRead)
async def update_qualification(
    staff_id: uuid.UUID,
    qual_id: uuid.UUID,
    req: QualificationUpdate,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)
    qual = await contacts_svc.update_qualification(staff_id, qual_id, req, school_id, db)
    return QualificationRead.model_validate(qual)


@router.delete("/{staff_id}/qualifications/{qual_id}", status_code=204)
async def delete_qualification(
    staff_id: uuid.UUID,
    qual_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)
    await contacts_svc.delete_qualification(staff_id, qual_id, school_id, db)


@router.patch("/{staff_id}/promotions/{promotion_id}", response_model=PromotionRead)
async def update_promotion(
    staff_id: uuid.UUID,
    promotion_id: uuid.UUID,
    req: PromotionUpdate,
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await leave_svc.update_promotion(staff_id, promotion_id, req, school_id, db)


@router.delete("/{staff_id}/promotions/{promotion_id}", status_code=204)
async def delete_promotion(
    staff_id: uuid.UUID,
    promotion_id: uuid.UUID,
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await leave_svc.delete_promotion(staff_id, promotion_id, school_id, db)


@router.post("/{staff_id}/promotions", response_model=PromotionRead, status_code=201)
async def record_promotion(
    staff_id: uuid.UUID,
    req: PromotionCreate,
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await leave_svc.record_promotion(staff_id, req, school_id, db, approved_by_id=user_id)


@router.get("/{staff_id}/promotions", response_model=list[PromotionRead])
async def list_promotions(
    staff_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "view", db)
    return await leave_svc.list_promotions(staff_id, school_id, db)


@router.post("/{staff_id}/leave", response_model=LeaveRead, status_code=201)
async def submit_leave(
    staff_id: uuid.UUID,
    req: LeaveCreate,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)
    leave = await leave_svc.submit_leave(staff_id, req, school_id, db)
    return LeaveRead.model_validate(leave)


@router.get("/{staff_id}/leave", response_model=list[LeaveRead])
async def list_leave(
    staff_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "view", db)
    leaves = await leave_svc.list_leave(staff_id, school_id, db)
    return [LeaveRead.model_validate(l) for l in leaves]


@router.get("/export/excel")
async def export_staff_excel(
    category_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(True),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export the staff register as an Excel workbook (.xlsx)."""
    from app.services.staff_export import export_excel
    _, school_id = ids
    xlsx = await export_excel(school_id, db, category_id=category_id, active_only=active_only)
    return StreamingResponse(
        iter([xlsx]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="staff_register.xlsx"'},
    )


@router.get("/export/pdf")
async def export_staff_pdf(
    category_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(True),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export the staff register as a PDF (A4 landscape)."""
    from app.services.staff_export import export_pdf
    _, school_id = ids
    pdf = await export_pdf(school_id, db, category_id=category_id, active_only=active_only)
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="staff_register.pdf"'},
    )
