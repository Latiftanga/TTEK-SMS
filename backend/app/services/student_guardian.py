"""
Guardian add/update/remove for a student. Helpers live in student.py.

PRIMARY GUARDIAN INVARIANT
---------------------------
Every student with at least one guardian must have exactly one marked
is_primary. Enforced across all three mutations here:
  add_guardian    — the first guardian linked to a student is always primary,
                     regardless of the caller's is_primary value.
  update_guardian — demoting the sole primary guardian is rejected unless
                     another guardian is promoted in the same request (i.e.
                     promote the replacement first, which auto-demotes this one).
  remove_guardian — removing the student's only guardian is rejected; removing
                     the primary while others remain auto-promotes one of them.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.students import Guardian, Student, StudentGuardian
from app.schemas.students import GuardianCreate, GuardianUpdate, StudentGuardianRead
from app.services.student import _to_guardian_read


async def add_guardian(
    student_id: uuid.UUID,
    req: GuardianCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentGuardianRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    existing_count = await db.scalar(
        select(func.count()).select_from(StudentGuardian).where(StudentGuardian.student_id == student_id)
    )
    is_primary = req.is_primary or existing_count == 0

    if is_primary:
        existing_primary = await db.scalars(
            select(StudentGuardian)
            .where(StudentGuardian.student_id == student_id, StudentGuardian.is_primary.is_(True))
        )
        for sg in existing_primary:
            sg.is_primary = False

    guardian = Guardian(
        school_id=school_id,
        first_name=req.first_name.strip(),
        last_name=req.last_name.strip(),
        phone=req.phone.strip(),
        email=req.email.lower().strip() if req.email else None,
        occupation=req.occupation,
        address=req.address,
    )
    db.add(guardian)
    await db.flush()

    link = StudentGuardian(
        school_id=school_id,
        student_id=student_id,
        guardian_id=guardian.id,
        relation_type=req.relation_type.strip(),
        is_primary=is_primary,
    )
    db.add(link)
    await db.flush()
    link.guardian = guardian
    return _to_guardian_read(link)


async def update_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    req: GuardianUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentGuardianRead:
    link = await db.scalar(
        select(StudentGuardian)
        .where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id == guardian_id,
            StudentGuardian.school_id == school_id,
        )
        .options(selectinload(StudentGuardian.guardian))
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian link not found.")

    data = req.model_dump(exclude_unset=True)

    if data.get("is_primary"):
        existing = await db.scalars(
            select(StudentGuardian).where(
                StudentGuardian.student_id == student_id,
                StudentGuardian.is_primary.is_(True),
                StudentGuardian.guardian_id != guardian_id,
            )
        )
        for sg in existing:
            sg.is_primary = False
    elif data.get("is_primary") is False and link.is_primary:
        other_primary = await db.scalar(
            select(StudentGuardian.id).where(
                StudentGuardian.student_id == student_id,
                StudentGuardian.is_primary.is_(True),
                StudentGuardian.guardian_id != guardian_id,
            )
        )
        if not other_primary:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot remove primary status — promote another guardian to primary first.",
            )

    guardian_fields = {"first_name", "last_name", "phone", "email", "occupation", "address"}
    link_fields     = {"relation_type", "is_primary"}
    g = link.guardian
    for field, val in data.items():
        if field in guardian_fields:
            setattr(g, field, val)
        elif field in link_fields:
            setattr(link, field, val)

    # Guardian.phone is also the portal login identifier (User.phone) —
    # keep an active portal account's login in sync, or a phone-number edit
    # here would silently lock the guardian out.
    portal_user = await db.scalar(
        select(User).where(User.guardian_id == guardian_id, User.is_active.is_(True))
    )
    if portal_user and "phone" in data:
        portal_user.phone = g.phone

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already used by another portal account on this platform.",
        )
    return _to_guardian_read(link, has_portal_access=portal_user is not None)


async def remove_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    link = await db.scalar(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id == guardian_id,
            StudentGuardian.school_id == school_id,
        )
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian link not found.")

    remaining = await db.scalars(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id != guardian_id,
        )
    )
    remaining_links = list(remaining)
    if not remaining_links:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove a student's only guardian.",
        )
    if link.is_primary:
        remaining_links[0].is_primary = True

    await db.delete(link)
    await db.flush()
