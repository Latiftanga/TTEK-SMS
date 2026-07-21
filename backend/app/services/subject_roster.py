"""
Which students are eligible to be scored for a given assessment's subject.

This exists because a class can split into electives (e.g. one student takes
French, another takes Literature-in-French, in the same class) — the roster
for a subject's assessment must not be "everyone in the class" once that
split is registered.

ELIGIBILITY RULE
----------------
A student is eligible for `subject_id` in `academic_term_id` unless:
  - they have an active TermEnrollment for that term, AND
  - that TermEnrollment has at least one SubjectRegistration recorded, AND
  - none of those registrations is for `subject_id`.

In every other case (no TermEnrollment yet, or a TermEnrollment with zero
registrations recorded) they're treated as eligible — registration data, once
present, is authoritative; its absence falls back to "the whole class
curriculum applies", which is this system's behaviour for every school that
doesn't use per-student subject registration (GES Basic, no electives).
"""
from __future__ import annotations
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, ClassSubject
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment
from app.schemas.assessments import AssessmentRosterStudent


def _display_name(first: str, middle: str | None, last: str) -> str:
    return " ".join(p for p in (first, middle, last) if p)


async def class_subject_exists(
    class_id: uuid.UUID, subject_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> bool:
    return await db.scalar(
        select(ClassSubject.id).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.school_id == school_id,
            ClassSubject.is_active.is_(True),
        )
    ) is not None


async def filter_eligible_for_subject(
    student_ids: list[uuid.UUID],
    academic_term_id: uuid.UUID,
    subject_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> set[uuid.UUID]:
    """Batch form of the eligibility rule — avoids N+1 for a whole roster."""
    if not student_ids:
        return set()

    te_by_student: dict[uuid.UUID, uuid.UUID] = dict((await db.execute(
        select(TermEnrollment.student_id, TermEnrollment.id).where(
            TermEnrollment.student_id.in_(student_ids),
            TermEnrollment.academic_term_id == academic_term_id,
            TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
        )
    )).all())
    te_ids = list(te_by_student.values())

    reg_counts: dict[uuid.UUID, int] = {}
    registered_for_subject: set[uuid.UUID] = set()
    if te_ids:
        reg_counts = dict((await db.execute(
            select(SubjectRegistration.term_enrollment_id, func.count())
            .where(SubjectRegistration.term_enrollment_id.in_(te_ids))
            .group_by(SubjectRegistration.term_enrollment_id)
        )).all())
        registered_for_subject = set((await db.scalars(
            select(SubjectRegistration.term_enrollment_id).where(
                SubjectRegistration.term_enrollment_id.in_(te_ids),
                SubjectRegistration.subject_id == subject_id,
            )
        )).all())

    eligible: set[uuid.UUID] = set()
    for sid in student_ids:
        te_id = te_by_student.get(sid)
        if te_id is None or reg_counts.get(te_id, 0) == 0 or te_id in registered_for_subject:
            eligible.add(sid)
    return eligible


async def list_assessment_roster(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[AssessmentRosterStudent]:
    term = await db.get(AcademicTerm, academic_term_id)
    if not term:
        return []

    all_ids = list((await db.scalars(
        select(StudentClassAssignment.student_id).where(
            StudentClassAssignment.class_id == class_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
        )
    )).all())
    eligible_ids = await filter_eligible_for_subject(
        all_ids, academic_term_id, subject_id, school_id, db,
    )
    if not eligible_ids:
        return []

    students = (await db.scalars(
        select(Student)
        .where(Student.id.in_(eligible_ids), Student.school_id == school_id)
        .order_by(Student.last_name, Student.first_name)
    )).all()
    return [
        AssessmentRosterStudent(
            id=s.id,
            display_name=_display_name(s.first_name, s.middle_name, s.last_name),
            admission_number=s.admission_number,
        )
        for s in students
    ]
