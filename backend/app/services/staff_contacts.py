"""Emergency contact and qualification CRUD for staff members.

Separated from services/staff.py to keep files under 300 lines.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import StaffEmergencyContact, StaffMember, StaffQualification
from app.schemas.staff import EmergencyContactCreate, QualificationCreate


async def add_emergency_contact(
    staff_id: uuid.UUID,
    req: EmergencyContactCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffEmergencyContact:
    await _assert_owns(staff_id, school_id, db)
    contact = StaffEmergencyContact(
        school_id=school_id,
        staff_member_id=staff_id,
        name=req.name.strip(),
        contact_type=req.contact_type.strip(),
        phone=req.phone.strip(),
        email=req.email.lower().strip() if req.email else None,
    )
    db.add(contact)
    await db.flush()
    return contact


async def delete_emergency_contact(
    staff_id: uuid.UUID,
    contact_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    contact = await db.scalar(
        select(StaffEmergencyContact).where(
            StaffEmergencyContact.id == contact_id,
            StaffEmergencyContact.staff_member_id == staff_id,
            StaffEmergencyContact.school_id == school_id,
        )
    )
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
    await db.delete(contact)
    await db.flush()


async def add_qualification(
    staff_id: uuid.UUID,
    req: QualificationCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffQualification:
    await _assert_owns(staff_id, school_id, db)
    qual = StaffQualification(
        school_id=school_id,
        staff_member_id=staff_id,
        institution=req.institution.strip(),
        qualification_type=req.qualification_type.strip(),
        field_of_study=req.field_of_study.strip() if req.field_of_study else None,
        year_obtained=req.year_obtained,
    )
    db.add(qual)
    await db.flush()
    return qual


async def delete_qualification(
    staff_id: uuid.UUID,
    qual_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    qual = await db.scalar(
        select(StaffQualification).where(
            StaffQualification.id == qual_id,
            StaffQualification.staff_member_id == staff_id,
            StaffQualification.school_id == school_id,
        )
    )
    if not qual:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Qualification not found.")
    await db.delete(qual)
    await db.flush()


async def _assert_owns(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> StaffMember:
    member = await db.get(StaffMember, staff_id)
    if not member or member.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    return member
