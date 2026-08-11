"""Staff photo upload/delete. Split out of routers/staff.py to stay under
the 300-line cap — mirrors routers/students_detail.py's photo endpoints.

ACCESS CONTROL
--------------
POST/DELETE /staff/{id}/photo         self or staff.edit
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import assert_self_or_permission, require_auth
from app.schemas.staff import StaffMemberDetail
from app.services import staff_photo as photo_svc

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post("/{staff_id}/photo", response_model=StaffMemberDetail)
async def upload_photo(
    staff_id: uuid.UUID,
    file: UploadFile = File(...),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Upload or replace a staff member's profile photo. A staff member may
    always manage their own photo; managing someone else's requires
    staff.edit — same gate as PATCH /staff/{id}."""
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)
    return await photo_svc.upload_staff_photo(staff_id, file, school_id, db)


@router.delete("/{staff_id}/photo", status_code=204)
async def delete_photo(
    staff_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assert_self_or_permission(user_id, staff_id, "staff", "edit", db)
    await photo_svc.remove_staff_photo(staff_id, school_id, db)
