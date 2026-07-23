"""
Subject registration — which subjects a student is taking against a given
TermEnrollment. Split out of student_enrollment.py (was over the 300-line
cap).

A student can only be registered for a subject actually offered to their
class (ClassSubject) — mirrors the same check on assessment creation
(services/subject_roster.py::class_subject_exists, added in 12q).
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Subject
from app.models.students import StudentClassAssignment, SubjectRegistration, TermEnrollment
from app.schemas.students import SubjectRegistrationItem, SubjectRegistrationRead
from app.services.subject_roster import class_subject_exists


async def register_subjects(
    te_id: uuid.UUID,
    items: list[SubjectRegistrationItem],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRegistrationRead]:
    te = await db.scalar(
        select(TermEnrollment).where(
            TermEnrollment.id == te_id, TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
        )
    )
    if not te:
        raise HTTPException(status_code=404, detail="Term enrollment not found.")

    # Validate every item up front, before touching the DB.
    term = await db.get(AcademicTerm, te.academic_term_id)
    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == te.student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ) if term else None
    if not sca:
        raise HTTPException(
            status_code=422,
            detail="Student has no class assignment for this academic year — cannot register subjects.",
        )
    for item in items:
        if not await class_subject_exists(sca.class_id, item.subject_id, school_id, db):
            subject = await db.get(Subject, item.subject_id)
            name = subject.name if subject else str(item.subject_id)
            raise HTTPException(
                status_code=422,
                detail=f"'{name}' is not assigned to this student's class.",
            )

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
