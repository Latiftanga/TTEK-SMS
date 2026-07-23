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
    Class,
    ClassSubject,
    SHSProgramme,
    Subject,
)
from app.schemas.academic import (
    ClassCreate,
    ClassRead,
    ClassSubjectAssign,
    ClassUpdate,
)


def _display_name(
    level: str,
    year_group: int,
    programme_name: str | None,
    stream: str | None,
) -> str:
    if level.upper() == "SHS":
        # SHS: "1 General Science A" — level is implied by the school
        parts = [str(year_group)]
        if programme_name:
            parts.append(programme_name)
    else:
        # Basic schools: "Basic 5", "KG 2", etc.
        parts = [level, str(year_group)]
    if stream:
        parts.append(stream)
    return " ".join(parts)


def _to_class_read(cls: Class, programme_name: str | None) -> ClassRead:
    return ClassRead(
        id=cls.id,
        school_id=cls.school_id,
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
    # Uniqueness: (school, level, year_group, programme, stream) must be unique.
    # Handle NULLs explicitly since SQL NULL != NULL.
    level_norm = req.level.strip()
    stream_norm = req.stream.strip() if req.stream else None
    prog_clause = (
        Class.programme_id == req.programme_id if req.programme_id else Class.programme_id.is_(None)
    )
    stream_clause = Class.stream == stream_norm if stream_norm else Class.stream.is_(None)
    duplicate = await db.scalar(
        select(Class).where(
            Class.school_id == school_id,
            Class.level == level_norm,
            Class.year_group == req.year_group,
            prog_clause,
            stream_clause,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A class with this name already exists.",
        )

    programme = None
    if req.programme_id:
        programme = await db.scalar(
            select(SHSProgramme).where(
                SHSProgramme.id == req.programme_id, SHSProgramme.school_id == school_id,
            )
        )
        if not programme:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Programme not found.")
    cls = Class(
        school_id=school_id,
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
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassRead]:
    result = await db.execute(
        _classes_query([Class.school_id == school_id])
        .order_by(Class.level, Class.year_group, Class.stream)
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
    if req.programme_id is not None:
        prog = await db.scalar(
            select(SHSProgramme).where(
                SHSProgramme.id == req.programme_id, SHSProgramme.school_id == school_id,
            )
        )
        if not prog:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Programme not found.")
        cls.programme_id = req.programme_id
    if req.stream is not None:
        cls.stream = req.stream.strip() or None
    if req.capacity is not None:
        cls.capacity = req.capacity
    if req.is_active is not None:
        cls.is_active = req.is_active
    await db.flush()
    prog = await db.get(SHSProgramme, cls.programme_id) if cls.programme_id else None
    return _to_class_read(cls, prog.name if prog else None)


async def list_class_subjects(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassSubject]:
    cls = await db.get(Class, class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    rows = await db.scalars(
        select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.school_id == school_id,
        )
    )
    return list(rows)


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

    # Every subject_id must be one of this school's own subjects — Subject
    # rows are school-private (unlike the shared SubjectCatalogue), and
    # nothing upstream of this call verifies that.
    owned_ids = set((await db.scalars(
        select(Subject.id).where(Subject.id.in_(req.subject_ids), Subject.school_id == school_id)
    )).all())
    unknown = [str(sid) for sid in req.subject_ids if sid not in owned_ids]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject(s) not found: {', '.join(unknown)}.",
        )

    added = []
    for subj_id in req.subject_ids:
        if subj_id not in existing_ids:
            cs = ClassSubject(school_id=school_id, class_id=class_id, subject_id=subj_id, is_active=True)
            db.add(cs)
            added.append(cs)
    await db.flush()
    return added


async def remove_class_subject(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    cs = await db.scalar(
        select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.school_id == school_id,
        )
    )
    if not cs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not assigned to this class.",
        )
    await db.delete(cs)
    await db.flush()
