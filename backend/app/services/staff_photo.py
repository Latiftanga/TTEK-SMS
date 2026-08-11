"""
Staff photo upload/delete — mirrors services/student_photo.py. Shares the
image pipeline in services/storage.py with the school logo and student
photo uploads.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.staff import StaffMember
from app.schemas.staff import StaffMemberDetail
from app.services.staff import _to_detail


async def upload_staff_photo(
    staff_id: uuid.UUID,
    file: UploadFile,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffMemberDetail:
    member = await db.scalar(
        select(StaffMember)
        .where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
        .options(
            selectinload(StaffMember.positions),
            selectinload(StaffMember.qualifications),
            selectinload(StaffMember.emergency_contacts),
            selectinload(StaffMember.category),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    from app.services.storage import save_staff_photo
    member.photo_path = await save_staff_photo(file, member.id)
    await db.flush()
    has_account = bool(await db.scalar(select(User.id).where(User.staff_member_id == staff_id)))
    return _to_detail(member, has_account=has_account)


async def remove_staff_photo(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    member = await db.get(StaffMember, staff_id)
    if not member or member.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    from app.services.storage import delete_staff_photo
    delete_staff_photo(member.id)
    member.photo_path = None
    await db.flush()
