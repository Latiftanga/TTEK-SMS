"""Staff member CRUD: create, list, get, update, emergency contacts, qualifications.

Promotions and leave management live in services/staff_leave.py.
"""
from __future__ import annotations
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import StaffPosition
from app.models.staff import StaffEmergencyContact, StaffMember, StaffQualification
from app.schemas.staff import (
    EmergencyContactCreate,
    EmergencyContactRead,
    QualificationCreate,
    QualificationRead,
    StaffMemberCreate,
    StaffMemberDetail,
    StaffMemberSummary,
    StaffMemberUpdate,
)


def _display_name(first: str, middle: str | None, last: str) -> str:
    parts = [first]
    if middle:
        parts.append(middle)
    parts.append(last)
    return " ".join(parts)


def _to_summary(member: StaffMember, position_name: str | None) -> StaffMemberSummary:
    return StaffMemberSummary(
        id=member.id,
        school_id=member.school_id,
        staff_number=member.staff_number,
        first_name=member.first_name,
        middle_name=member.middle_name,
        last_name=member.last_name,
        display_name=_display_name(member.first_name, member.middle_name, member.last_name),
        gender=member.gender,
        phone=member.phone,
        email=member.email,
        position_id=member.position_id,
        position_name=position_name,
        department=member.department,
        is_active=member.is_active,
        joined_date=member.joined_date,
    )


def _to_detail(member: StaffMember, position_name: str | None) -> StaffMemberDetail:
    return StaffMemberDetail(
        **_to_summary(member, position_name).model_dump(),
        date_of_birth=member.date_of_birth,
        national_id=member.national_id,
        photo_path=member.photo_path,
        qualifications=[QualificationRead.model_validate(q) for q in member.qualifications],
        emergency_contacts=[EmergencyContactRead.model_validate(c) for c in member.emergency_contacts],
    )


async def create_staff(
    req: StaffMemberCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffMemberDetail:
    member = StaffMember(
        school_id=school_id,
        staff_number=req.staff_number.strip(),
        first_name=req.first_name.strip(),
        middle_name=req.middle_name.strip() if req.middle_name else None,
        last_name=req.last_name.strip(),
        date_of_birth=req.date_of_birth,
        gender=req.gender,
        national_id=req.national_id,
        phone=req.phone,
        email=req.email.lower().strip() if req.email else None,
        position_id=req.position_id,
        department=req.department,
        is_active=True,
        joined_date=req.joined_date,
    )
    db.add(member)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Staff number '{req.staff_number}' is already in use at this school.",
        )
    await db.refresh(member, attribute_names=["qualifications", "emergency_contacts"])
    position_name = await _position_name(member.position_id, db)
    return _to_detail(member, position_name)


async def list_staff(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> list[StaffMemberSummary]:
    q = (
        select(StaffMember, StaffPosition.name.label("pos_name"))
        .outerjoin(StaffPosition, StaffMember.position_id == StaffPosition.id)
        .where(StaffMember.school_id == school_id)
        .order_by(StaffMember.last_name, StaffMember.first_name)
        .offset(skip)
        .limit(limit)
    )
    if active_only:
        q = q.where(StaffMember.is_active == True)
    result = await db.execute(q)
    return [_to_summary(m, pos_name) for m, pos_name in result]


async def get_staff(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffMemberDetail:
    member = await db.scalar(
        select(StaffMember)
        .where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
        .options(
            selectinload(StaffMember.qualifications),
            selectinload(StaffMember.emergency_contacts),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    position_name = await _position_name(member.position_id, db)
    return _to_detail(member, position_name)


async def update_staff(
    staff_id: uuid.UUID,
    req: StaffMemberUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffMemberDetail:
    member = await db.scalar(
        select(StaffMember)
        .where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
        .options(
            selectinload(StaffMember.qualifications),
            selectinload(StaffMember.emergency_contacts),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(member, field, val)
    await db.flush()
    position_name = await _position_name(member.position_id, db)
    return _to_detail(member, position_name)


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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _position_name(position_id: uuid.UUID | None, db: AsyncSession) -> str | None:
    if not position_id:
        return None
    pos = await db.get(StaffPosition, position_id)
    return pos.name if pos else None


async def _assert_owns(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> StaffMember:
    member = await db.get(StaffMember, staff_id)
    if not member or member.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    return member
