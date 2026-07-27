"""Academic teacher assignment service: class teacher and subject teacher assignments."""
from __future__ import annotations
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import ClassTeacher, SubjectTeacher
from app.schemas.academic import ClassTeacherAssign, SubjectTeacherAssign


async def assign_class_teacher(
    class_id: uuid.UUID,
    req: ClassTeacherAssign,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassTeacher:
    existing = await db.scalar(
        select(ClassTeacher).where(
            ClassTeacher.class_id == class_id,
            ClassTeacher.academic_year_id == req.academic_year_id,
        )
    )
    if existing:
        existing.staff_member_id = req.staff_member_id
        existing.is_active = True
        await db.flush()
        return existing

    ct = ClassTeacher(
        school_id=school_id,
        class_id=class_id,
        staff_member_id=req.staff_member_id,
        academic_year_id=req.academic_year_id,
        is_active=True,
    )
    db.add(ct)
    await db.flush()
    return ct


async def assign_subject_teacher(
    class_id: uuid.UUID,
    req: SubjectTeacherAssign,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> SubjectTeacher:
    existing = await db.scalar(
        select(SubjectTeacher).where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.subject_id == req.subject_id,
            SubjectTeacher.academic_year_id == req.academic_year_id,
        )
    )
    if existing:
        existing.staff_member_id = req.staff_member_id
        existing.is_active = True
        await db.flush()
        return existing

    st = SubjectTeacher(
        school_id=school_id,
        class_id=class_id,
        subject_id=req.subject_id,
        staff_member_id=req.staff_member_id,
        academic_year_id=req.academic_year_id,
        is_active=True,
    )
    db.add(st)
    await db.flush()
    return st


async def get_class_teacher(
    class_id: uuid.UUID,
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassTeacher | None:
    return await db.scalar(
        select(ClassTeacher).where(
            ClassTeacher.class_id == class_id,
            ClassTeacher.academic_year_id == year_id,
            ClassTeacher.school_id == school_id,
        )
    )


async def list_subject_teachers(
    class_id: uuid.UUID,
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectTeacher]:
    rows = await db.scalars(
        select(SubjectTeacher).where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.academic_year_id == year_id,
            SubjectTeacher.school_id == school_id,
        )
    )
    return list(rows)
