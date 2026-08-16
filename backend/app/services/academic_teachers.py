"""Academic teacher assignment service: class teacher and subject teacher assignments."""
from __future__ import annotations
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, ClassTeacher, SubjectTeacher
from app.models.staff import StaffMember
from app.schemas.academic import ClassTeacherAssign, SubjectTeacherAssign
from app.services.academic_class import get_active_class
from app.services.subject_roster import class_subject_exists


async def _assert_staff_owned(staff_member_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    exists = await db.scalar(
        select(StaffMember.id).where(StaffMember.id == staff_member_id, StaffMember.school_id == school_id)
    )
    if not exists:
        raise HTTPException(404, "Staff member not found.")


async def _assert_year_owned(academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    exists = await db.scalar(
        select(AcademicYear.id).where(AcademicYear.id == academic_year_id, AcademicYear.school_id == school_id)
    )
    if not exists:
        raise HTTPException(404, "Academic year not found.")


async def assign_class_teacher(
    class_id: uuid.UUID,
    req: ClassTeacherAssign,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassTeacher:
    await get_active_class(class_id, school_id, db)
    await _assert_staff_owned(req.staff_member_id, school_id, db)
    await _assert_year_owned(req.academic_year_id, school_id, db)

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
    await get_active_class(class_id, school_id, db)
    await _assert_staff_owned(req.staff_member_id, school_id, db)
    await _assert_year_owned(req.academic_year_id, school_id, db)
    # Reuses the same check register_subjects/create_assessment already use:
    # a subject teacher can only be assigned to a subject actually on this
    # class's curriculum (and, as a side effect, this closes the same
    # cross-school-id gap assign_subjects() was already fixed for — a
    # subject_id from another school can never be an active ClassSubject here.
    if not await class_subject_exists(class_id, req.subject_id, school_id, db):
        raise HTTPException(404, "That subject is not on this class's curriculum.")

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
