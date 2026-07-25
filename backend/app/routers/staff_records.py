"""Staff HR sub-records — responsibilities, emergency contacts, qualifications,
promotions, and leave. Split out of routers/staff.py to stay under the
300-line cap.

ACCESS CONTROL
--------------
GET  /staff/{id}/responsibilities            self or staff.view
POST/PATCH/DELETE contacts & qualifications   self or staff.edit
POST/PATCH/DELETE /staff/{id}/promotions      staff.edit
GET  /staff/{id}/promotions                   self or staff.view
POST /staff/{id}/leave                        self or staff.edit
GET  /staff/{id}/leave                        self or staff.view
GET  /staff/leave/pending                     staff.edit
PATCH /staff/leave/{id}/review                staff.edit
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import assert_self_or_permission, require_auth, require_permission
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
    StaffResponsibilities,
)
from app.services import staff_contacts as contacts_svc
from app.services import staff_leave as leave_svc
from app.services import staff_responsibilities as responsibilities_svc

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/leave/pending", response_model=list[LeaveRead])
async def list_pending_leave(
    ids=Depends(require_permission("staff", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await leave_svc.list_pending_leave(school_id, db)


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
