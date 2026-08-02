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

from app.core.teacher_scope import resolve_assessment_scope, year_for_term
from app.models.academic import AcademicTerm, Class, ClassSubject, SHSProgramme, Subject, SubjectTeacher
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment
from app.schemas.assessments import AssessmentRosterStudent, MySubjectAssignment
from app.services.student_display import _class_display_name


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


async def subject_teacher_assigned(
    class_id: uuid.UUID, subject_id: uuid.UUID, academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> bool:
    """Whether someone is actually assigned to teach this (class, subject)
    pair this year — a student shouldn't be registered for a subject no one
    is teaching. Checked at registration time, not at ClassSubject-creation
    time, since a subject can legitimately sit on the curriculum before a
    teacher is assigned; it just can't be registered to a student yet."""
    return await db.scalar(
        select(SubjectTeacher.id).where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.subject_id == subject_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.school_id == school_id,
            SubjectTeacher.is_active.is_(True),
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
        select(StudentClassAssignment.student_id)
        .join(Student, Student.id == StudentClassAssignment.student_id)
        .where(
            StudentClassAssignment.class_id == class_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
            Student.is_active.is_(True),
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


async def list_my_subjects(
    term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[MySubjectAssignment]:
    """(class, subject) combos the caller can create assessments/enter scores
    for — every active ClassSubject in the school if unrestricted, else just
    the caller's own SubjectTeacher pairs this year. Powers the Assessments
    page's cascading class → subject pickers."""
    year_id = await year_for_term(term_id, db)
    if year_id is None:
        return []

    scope = await resolve_assessment_scope(user_id, year_id, db)

    if scope is None:
        rows = await db.execute(
            select(Class, Subject, SHSProgramme.name.label("prog_name"))
            .join(ClassSubject, ClassSubject.class_id == Class.id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
            .where(
                Class.school_id == school_id,
                ClassSubject.school_id == school_id,
                ClassSubject.is_active.is_(True),
            )
            .order_by(Class.level, Class.year_group, Class.stream, Subject.name)
        )
        return [
            MySubjectAssignment(
                class_id=cls.id,
                class_name=_class_display_name(cls.level, cls.year_group, prog_name, cls.stream),
                subject_id=subj.id,
                subject_name=subj.name,
            )
            for cls, subj, prog_name in rows
        ]

    if not scope:
        return []

    class_ids = {cid for cid, _ in scope}
    subject_ids = {sid for _, sid in scope}
    class_rows = await db.execute(
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(Class.id.in_(class_ids), Class.school_id == school_id)
    )
    classes_by_id = {
        cls.id: _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)
        for cls, prog_name in class_rows
    }
    subjects_by_id = {
        s.id: s.name
        for s in await db.scalars(select(Subject).where(Subject.id.in_(subject_ids), Subject.school_id == school_id))
    }
    result = [
        MySubjectAssignment(
            class_id=cid, class_name=classes_by_id[cid],
            subject_id=sid, subject_name=subjects_by_id[sid],
        )
        for cid, sid in scope
        if cid in classes_by_id and sid in subjects_by_id
    ]
    result.sort(key=lambda r: (r.class_name, r.subject_name))
    return result
