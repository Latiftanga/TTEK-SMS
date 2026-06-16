"""Staff member CRUD: create, list, get, update, emergency contacts, qualifications.

Promotions and leave management live in services/staff_leave.py.
"""
from __future__ import annotations
import uuid
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.staff import StaffMember, staff_member_positions
from app.schemas.staff import (
    QualificationRead,
    EmergencyContactRead,
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


def _to_summary(member: StaffMember) -> StaffMemberSummary:
    return StaffMemberSummary(
        id=member.id,
        school_id=member.school_id,
        staff_number=member.staff_number,
        first_name=member.first_name,
        middle_name=member.middle_name,
        last_name=member.last_name,
        display_name=_display_name(member.first_name, member.middle_name, member.last_name),
        gender=member.gender,
        staff_category=member.staff_category,
        employment_type=member.employment_type,
        phone=member.phone,
        email=member.email,
        position_ids=[p.id for p in member.positions],
        position_names=[p.name for p in member.positions],
        is_active=member.is_active,
        joined_date=member.joined_date,
    )


def _to_detail(member: StaffMember) -> StaffMemberDetail:
    return StaffMemberDetail(
        **_to_summary(member).model_dump(),
        date_of_birth=member.date_of_birth,
        marital_status=member.marital_status,
        national_id=member.national_id,
        ssnit_number=member.ssnit_number,
        address=member.address,
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
        staff_category=req.staff_category,
        employment_type=req.employment_type,
        marital_status=req.marital_status,
        national_id=req.national_id,
        ssnit_number=req.ssnit_number,
        address=req.address,
        phone=req.phone,
        email=req.email.lower().strip() if req.email else None,
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
    final_position_ids = list(req.position_ids)
    if req.staff_category and req.staff_category.value == "TEACHING":
        final_position_ids = await _merge_teacher_position(final_position_ids, school_id, db)
    if final_position_ids:
        await db.execute(
            staff_member_positions.insert(),
            [{"staff_member_id": member.id, "position_id": pid} for pid in final_position_ids],
        )
    await db.refresh(member, attribute_names=["positions", "qualifications", "emergency_contacts"])
    return _to_detail(member)


async def list_staff(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> list[StaffMemberSummary]:
    q = (
        select(StaffMember)
        .where(StaffMember.school_id == school_id)
        .options(selectinload(StaffMember.positions))
        .order_by(StaffMember.last_name, StaffMember.first_name)
        .offset(skip)
        .limit(limit)
    )
    if active_only:
        q = q.where(StaffMember.is_active == True)
    members = await db.scalars(q)
    return [_to_summary(m) for m in members]


async def get_staff(
    staff_id: uuid.UUID,
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
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    return _to_detail(member)


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
            selectinload(StaffMember.positions),
            selectinload(StaffMember.qualifications),
            selectinload(StaffMember.emergency_contacts),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    update_data = req.model_dump(exclude_unset=True)
    new_position_ids: list[uuid.UUID] | None = update_data.pop("position_ids", None)

    for field, val in update_data.items():
        setattr(member, field, val)

    # If category is being set to TEACHING, ensure Teacher position is included
    new_category = update_data.get("staff_category") or member.staff_category
    if new_position_ids is not None:
        if new_category and new_category.value == "TEACHING":
            new_position_ids = await _merge_teacher_position(new_position_ids, school_id, db)
        await db.execute(
            delete(staff_member_positions).where(
                staff_member_positions.c.staff_member_id == staff_id
            )
        )
        if new_position_ids:
            await db.execute(
                staff_member_positions.insert(),
                [{"staff_member_id": staff_id, "position_id": pid} for pid in new_position_ids],
            )
        await db.refresh(member, attribute_names=["positions"])
    elif "staff_category" in update_data and update_data["staff_category"] and update_data["staff_category"].value == "TEACHING":
        # Category changed to TEACHING but positions not explicitly updated — auto-add Teacher
        current_ids = [p.id for p in member.positions]
        merged = await _merge_teacher_position(current_ids, school_id, db)
        added = [pid for pid in merged if pid not in current_ids]
        if added:
            await db.execute(
                staff_member_positions.insert(),
                [{"staff_member_id": staff_id, "position_id": pid} for pid in added],
            )
            await db.refresh(member, attribute_names=["positions"])

    await db.flush()
    return _to_detail(member)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _merge_teacher_position(
    position_ids: list[uuid.UUID],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[uuid.UUID]:
    """Return position_ids with the TEACHER position guaranteed to be included."""
    from app.models.auth import StaffPosition
    from sqlalchemy import or_
    teacher = await db.scalar(
        select(StaffPosition).where(
            StaffPosition.code == "TEACHER",
            or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)),
        ).order_by(StaffPosition.school_id.nulls_last()).limit(1)
    )
    if teacher and teacher.id not in position_ids:
        return [*position_ids, teacher.id]
    return position_ids


