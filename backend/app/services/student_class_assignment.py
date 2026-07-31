"""
StudentClassAssignment CRUD — class membership by academic year.

StudentClassAssignment = "Student X is in Form 2A for 2024/2025" (stable, year-level).
A student has at most one class assignment per academic year (UniqueConstraint).

See student_enrollment.py for term-level attendance confirmation (TermEnrollment).
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, SHSProgramme
from app.models.students import Student, StudentClassAssignment
from app.schemas.students import (
    StudentClassAssignmentCreate,
    StudentClassAssignmentRead,
)
from app.services.student_display import _class_display_name


def _sca_query(*where_clauses):
    return (
        select(StudentClassAssignment, Class.level, Class.year_group, Class.stream, SHSProgramme.name)
        .join(Class, Class.id == StudentClassAssignment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(*where_clauses)
        .order_by(StudentClassAssignment.created_at.desc())
    )


def _to_sca_read(row) -> StudentClassAssignmentRead:
    sca, level, year_group, stream, prog_name = row
    return StudentClassAssignmentRead(
        id=sca.id,
        student_id=sca.student_id,
        class_id=sca.class_id,
        academic_year_id=sca.academic_year_id,
        class_display_name=_class_display_name(level, year_group, prog_name, stream),
        is_active=sca.is_active,
        created_at=sca.created_at,
    )


async def create_class_assignment(
    req: StudentClassAssignmentCreate,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> StudentClassAssignmentRead:
    student = await db.get(Student, req.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")

    cls = await db.get(Class, req.class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status_code=404, detail="Class not found.")

    year = await db.get(AcademicYear, req.academic_year_id)
    if not year or year.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    sca = StudentClassAssignment(
        school_id=school_id,
        student_id=req.student_id,
        class_id=req.class_id,
        academic_year_id=req.academic_year_id,
        assigned_by_id=user_id,
        is_active=True,
    )
    try:
        async with db.begin_nested():
            db.add(sca)
            await db.flush()
    except IntegrityError:
        # A row for (student, academic_year) already exists — if it's a stale
        # inactive one (e.g. the student withdrew and is now returning),
        # reactivate it in place rather than hard-blocking with a 409.
        existing = await db.scalar(
            select(StudentClassAssignment).where(
                StudentClassAssignment.student_id == req.student_id,
                StudentClassAssignment.academic_year_id == req.academic_year_id,
                StudentClassAssignment.school_id == school_id,
            )
        )
        if not existing or existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Student already has a class assignment for this academic year.",
            )
        existing.class_id = req.class_id
        existing.assigned_by_id = user_id
        existing.is_active = True
        await db.flush()
        sca = existing

    rows = await db.execute(_sca_query(StudentClassAssignment.id == sca.id))
    return _to_sca_read(rows.one())


async def list_class_assignments(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[StudentClassAssignmentRead]:
    rows = await db.execute(
        _sca_query(
            StudentClassAssignment.student_id == student_id,
            StudentClassAssignment.school_id == school_id,
        )
    )
    return [_to_sca_read(row) for row in rows]


async def bulk_class_assignment(
    items: list[StudentClassAssignmentCreate],
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Each item runs in its own SAVEPOINT (db.begin_nested()) — a plain
    try/except around create_class_assignment isn't enough: a failed flush
    (duplicate assignment) leaves the whole session's transaction unusable
    for the rest of the batch without a savepoint to roll back to. See
    student_enrollment.py::bulk_term_enrollment for the same pattern."""
    assigned = skipped = 0
    for item in items:
        try:
            async with db.begin_nested():
                await create_class_assignment(item, school_id, user_id, db)
            assigned += 1
        except HTTPException as e:
            if e.status_code != 409:
                raise
            skipped += 1
    return {"enrolled": assigned, "skipped": skipped}
