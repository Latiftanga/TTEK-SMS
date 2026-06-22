"""Guardian add/update/remove for a student. Helpers live in student.py."""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

    if req.is_primary:
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
        is_primary=req.is_primary,
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

    guardian_fields = {"first_name", "last_name", "phone", "email", "occupation", "address"}
    link_fields     = {"relation_type", "is_primary"}
    g = link.guardian
    for field, val in data.items():
        if field in guardian_fields:
            setattr(g, field, val)
        elif field in link_fields:
            setattr(link, field, val)

    await db.flush()
    return _to_guardian_read(link)


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
    await db.delete(link)
    await db.flush()
