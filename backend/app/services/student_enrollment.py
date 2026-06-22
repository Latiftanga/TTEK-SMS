"""
Initial enrollment, term enrollment, and subject registration.

FLOW
----
1. Admin creates Student record.
2. Admin creates StudentClassAssignment (student → class → academic year).
   See student_class_assignment.py.
3. Teacher creates TermEnrollment when the student physically reports for a term.
   Requires a StudentClassAssignment for the same academic year to exist first.
4. Teacher registers subjects (SubjectRegistration) against the TermEnrollment.

Transfer requests live in student_transfer.py.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, SHSProgramme
from app.models.students import (
    Student,
    StudentClassAssignment,
    StudentEnrollment,
    SubjectRegistration,
    TermEnrollment,
)
from app.schemas.students import (
    EnrollmentCreate,
    EnrollmentRead,
    SubjectRegistrationItem,
    SubjectRegistrationRead,
    TermEnrollmentCreate,
    TermEnrollmentRead,
)


def _display_name(level: str, year_group: int, programme_name: str | None, stream: str | None) -> str:
    if level.upper() == "SHS":
        parts = [str(year_group)]
        if programme_name:
            parts.append(programme_name)
    else:
        parts = [level, str(year_group)]
    if stream:
        parts.append(stream)
    return " ".join(parts)


def _te_query(*where_clauses):
    """
    Joins TermEnrollment → AcademicTerm → StudentClassAssignment → Class → SHSProgramme
    to include class context in the response.
    """
    return (
        select(
            TermEnrollment,
            StudentClassAssignment.class_id,
            Class.level,
            Class.year_group,
            Class.stream,
            SHSProgramme.name,
        )
        .join(AcademicTerm, AcademicTerm.id == TermEnrollment.academic_term_id)
        .outerjoin(
            StudentClassAssignment,
            (StudentClassAssignment.student_id == TermEnrollment.student_id)
            & (StudentClassAssignment.academic_year_id == AcademicTerm.academic_year_id),
        )
        .outerjoin(Class, Class.id == StudentClassAssignment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(*where_clauses)
        .order_by(TermEnrollment.created_at.desc())
    )


def _to_te_read(row) -> TermEnrollmentRead:
    te, class_id, level, year_group, stream, prog_name = row
    display = _display_name(level, year_group, prog_name, stream) if level else None
    return TermEnrollmentRead(
        id=te.id,
        student_id=te.student_id,
        academic_term_id=te.academic_term_id,
        class_id=class_id,
        class_display_name=display,
        is_active=te.is_active,
        created_at=te.created_at,
    )


# ── Initial enrollment ────────────────────────────────────────────────────────

async def create_enrollment(
    student_id: uuid.UUID,
    req: EnrollmentCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> EnrollmentRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    enrollment = StudentEnrollment(
        school_id=school_id,
        student_id=student_id,
        enrolled_at=req.enrolled_at,
        enrollment_type=req.enrollment_type,
        transfer_from_school=req.transfer_from_school,
    )
    db.add(enrollment)
    await db.flush()
    return EnrollmentRead.model_validate(enrollment)


# ── Term enrollment ───────────────────────────────────────────────────────────

async def create_term_enrollment(
    req: TermEnrollmentCreate,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> TermEnrollmentRead:
    student = await db.get(Student, req.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")

    term = await db.get(AcademicTerm, req.academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic term not found.")

    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == req.student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
        )
    )
    if not sca:
        raise HTTPException(
            status_code=422,
            detail="Student has no class assignment for this academic year. "
                   "Assign the student to a class before creating a term enrollment.",
        )

    te = TermEnrollment(
        school_id=school_id,
        student_id=req.student_id,
        academic_term_id=req.academic_term_id,
        enrolled_by_id=user_id,
        is_active=True,
    )
    db.add(te)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled for this term.",
        )

    rows = await db.execute(_te_query(TermEnrollment.id == te.id))
    return _to_te_read(rows.one())


async def list_term_enrollments(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[TermEnrollmentRead]:
    rows = await db.execute(
        _te_query(
            TermEnrollment.student_id == student_id,
            TermEnrollment.school_id == school_id,
        )
    )
    return [_to_te_read(row) for row in rows]


async def bulk_term_enrollment(
    items: list[TermEnrollmentCreate],
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    enrolled = skipped = 0
    for item in items:
        try:
            await create_term_enrollment(item, school_id, user_id, db)
            enrolled += 1
        except HTTPException as e:
            if e.status_code != 409:
                raise
            skipped += 1
    return {"enrolled": enrolled, "skipped": skipped}


# ── Subject registration ──────────────────────────────────────────────────────

async def register_subjects(
    te_id: uuid.UUID,
    items: list[SubjectRegistrationItem],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRegistrationRead]:
    te = await db.scalar(
        select(TermEnrollment).where(
            TermEnrollment.id == te_id, TermEnrollment.school_id == school_id
        )
    )
    if not te:
        raise HTTPException(status_code=404, detail="Term enrollment not found.")

    results: list[SubjectRegistration] = []
    for item in items:
        reg = SubjectRegistration(
            school_id=school_id,
            term_enrollment_id=te_id,
            subject_id=item.subject_id,
            registration_type=item.registration_type,
        )
        try:
            async with db.begin_nested():
                db.add(reg)
                await db.flush()
            results.append(reg)
        except IntegrityError:
            try:
                db.expunge(reg)
            except Exception:
                pass  # already registered — skip silently

    return [SubjectRegistrationRead.model_validate(r) for r in results]


async def list_subject_registrations(
    te_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRegistrationRead]:
    rows = await db.scalars(
        select(SubjectRegistration).where(
            SubjectRegistration.term_enrollment_id == te_id,
            SubjectRegistration.school_id == school_id,
        )
    )
    return [SubjectRegistrationRead.model_validate(r) for r in rows]


async def delete_subject_registration(
    te_id: uuid.UUID,
    reg_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    reg = await db.scalar(
        select(SubjectRegistration).where(
            SubjectRegistration.id == reg_id,
            SubjectRegistration.term_enrollment_id == te_id,
            SubjectRegistration.school_id == school_id,
        )
    )
    if not reg:
        raise HTTPException(status_code=404, detail="Subject registration not found.")
    await db.delete(reg)
    await db.flush()
