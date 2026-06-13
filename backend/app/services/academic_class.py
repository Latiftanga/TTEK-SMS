"""Academic class service: classes, teacher and subject assignments.

display_name is NEVER stored — computed on read.
Programmes, subject catalogue, and school subjects live in academic_subjects.py.
"""
from __future__ import annotations
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicYear,
    Class,
    ClassSubject,
    ClassTeacher,
    SHSProgramme,
    SubjectTeacher,
)
from app.schemas.academic import (
    ClassCreate,
    ClassRead,
    ClassSubjectAssign,
    ClassTeacherAssign,
    ClassUpdate,
    SubjectTeacherAssign,
)


def _display_name(
    level: str,
    year_group: int,
    programme_name: str | None,
    stream: str | None,
) -> str:
    parts = [level]
    if programme_name:
        parts.append(programme_name)
    if stream:
        parts.append(stream)
    parts.append(f"({year_group})")
    return " ".join(parts)


def _to_class_read(cls: Class, programme_name: str | None) -> ClassRead:
    return ClassRead(
        id=cls.id,
        school_id=cls.school_id,
        academic_year_id=cls.academic_year_id,
        level=cls.level,
        year_group=cls.year_group,
        programme_id=cls.programme_id,
        programme_name=programme_name,
        stream=cls.stream,
        capacity=cls.capacity,
        is_active=cls.is_active,
        display_name=_display_name(cls.level, cls.year_group, programme_name, cls.stream),
    )


async def create_class(
    req: ClassCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassRead:
    # Verify the academic year belongs to this school — prevents cross-school data access.
    year = await db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == req.academic_year_id,
            AcademicYear.school_id == school_id,
        )
    )
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found.")
    programme = await db.get(SHSProgramme, req.programme_id) if req.programme_id else None
    cls = Class(
        school_id=school_id,
        academic_year_id=req.academic_year_id,
        level=req.level.strip(),
        year_group=req.year_group,
        programme_id=req.programme_id,
        stream=req.stream.strip() if req.stream else None,
        capacity=req.capacity,
        is_active=True,
    )
    db.add(cls)
    await db.flush()
    return _to_class_read(cls, programme.name if programme else None)


def _classes_query(where_clauses: list):
    return (
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(*where_clauses)
    )


async def list_classes(
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassRead]:
    result = await db.execute(
        _classes_query([Class.school_id == school_id, Class.academic_year_id == year_id])
        .order_by(Class.level, Class.stream)
    )
    return [_to_class_read(cls, prog_name) for cls, prog_name in result]


async def get_class(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassRead:
    result = await db.execute(
        _classes_query([Class.id == class_id, Class.school_id == school_id])
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    cls, prog_name = row
    return _to_class_read(cls, prog_name)


async def update_class(
    class_id: uuid.UUID,
    req: ClassUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassRead:
    cls = await db.scalar(
        select(Class).where(Class.id == class_id, Class.school_id == school_id)
    )
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if req.stream is not None:
        cls.stream = req.stream.strip() or None
    if req.capacity is not None:
        cls.capacity = req.capacity
    if req.is_active is not None:
        cls.is_active = req.is_active
    await db.flush()
    prog = await db.get(SHSProgramme, cls.programme_id) if cls.programme_id else None
    return _to_class_read(cls, prog.name if prog else None)


async def assign_subjects(
    class_id: uuid.UUID,
    req: ClassSubjectAssign,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassSubject]:
    cls = await db.get(Class, class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")

    existing_rows = await db.scalars(
        select(ClassSubject).where(ClassSubject.class_id == class_id)
    )
    existing_ids = {cs.subject_id for cs in existing_rows}

    added = []
    for subj_id in req.subject_ids:
        if subj_id not in existing_ids:
            cs = ClassSubject(school_id=school_id, class_id=class_id, subject_id=subj_id, is_active=True)
            db.add(cs)
            added.append(cs)
    await db.flush()
    return added


async def assign_class_teacher(
    class_id: uuid.UUID,
    req: ClassTeacherAssign,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ClassTeacher:
    existing = await db.scalar(
        select(ClassTeacher).where(
            ClassTeacher.class_id == class_id,
            ClassTeacher.academic_term_id == req.academic_term_id,
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
        academic_term_id=req.academic_term_id,
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
            SubjectTeacher.academic_term_id == req.academic_term_id,
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
        academic_term_id=req.academic_term_id,
        is_active=True,
    )
    db.add(st)
    await db.flush()
    return st
