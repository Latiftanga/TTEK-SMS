"""
Class-wide, multi-student subject-registration operations — the bulk-register
action and the per-subject roster (read + write), as opposed to
services/student_subject_registration.py's single-student CRUD, which these
all build on top of rather than duplicating insert/delete/term-lock logic.

BULK REGISTER CORE SUBJECTS
---------------------------
bulk_register_core_subjects() registers every actively-enrolled student for
every ClassSubject on the class NOT marked is_elective — the common case
where a subject applies to the whole class and nobody should have to click
through each student individually. Electives stay fully manual/per-subject
(see get_subject_roster/set_subject_roster below); a student who should be
exempted from an otherwise universal subject (e.g. a disability-based
exemption) is handled by running this, then removing that one registration
via student_subject_registration.py::delete_subject_registration — no
separate exemption mechanism needed.

PER-SUBJECT ROSTER
-------------------
get_subject_roster()/set_subject_roster() give the same tick/select-all
control, scoped to ONE subject at a time, right where a subject's teacher
is assigned (SubjectsTab.svelte) — this is what makes electives (a class
splitting into e.g. French vs Literature-in-French) actually usable in
bulk, since bulk_register_core_subjects() deliberately never touches them.
set_subject_roster() takes the full desired-checked set (not a delta) and
diffs it against current DB state, so the registration_type sent to
register_subjects() is always derived from the ClassSubject's own
is_elective flag — never a separate caller choice.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, ClassSubject
from app.models.assessments import Assessment, Score
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment
from app.schemas.students import (
    BulkRegisterCoreSubjectsRequest,
    BulkRegisterCoreSubjectsResult,
    SetSubjectRosterRequest,
    SetSubjectRosterResult,
    SubjectRegistrationItem,
    SubjectRosterStudent,
)
from app.services.student_subject_registration import delete_subject_registration, register_subjects
from app.services.subject_roster import _display_name


async def bulk_register_core_subjects(
    class_id: uuid.UUID,
    req: BulkRegisterCoreSubjectsRequest,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> BulkRegisterCoreSubjectsResult:
    term = await db.get(AcademicTerm, req.academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic term not found.")

    core_subject_ids = list((await db.scalars(
        select(ClassSubject.subject_id).where(
            ClassSubject.class_id == class_id,
            ClassSubject.school_id == school_id,
            ClassSubject.is_active.is_(True),
            ClassSubject.is_elective.is_(False),
        )
    )).all())
    if not core_subject_ids:
        return BulkRegisterCoreSubjectsResult(registered=0, skipped=0)
    items = [
        SubjectRegistrationItem(subject_id=sid, registration_type="CORE")
        for sid in core_subject_ids
    ]

    active_ids = list((await db.scalars(
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
    te_by_student = dict((await db.execute(
        select(TermEnrollment.student_id, TermEnrollment.id).where(
            TermEnrollment.student_id.in_(active_ids),
            TermEnrollment.academic_term_id == req.academic_term_id,
            TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
        )
    )).all())

    for te_id in te_by_student.values():
        await register_subjects(te_id, items, school_id, user_id, db, req.override_reason)

    return BulkRegisterCoreSubjectsResult(
        registered=len(te_by_student),
        skipped=len(active_ids) - len(te_by_student),
    )


async def _class_subject(class_id: uuid.UUID, subject_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> ClassSubject:
    cs = await db.scalar(
        select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.school_id == school_id,
        )
    )
    if not cs:
        raise HTTPException(status_code=404, detail="Subject not assigned to this class.")
    return cs


async def _roster_base(
    class_id: uuid.UUID, academic_term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> tuple[AcademicTerm, list[uuid.UUID], dict[uuid.UUID, uuid.UUID]]:
    """Shared roster-building step: the term, every actively-assigned
    student in this class/year, and which of them have an active
    TermEnrollment this term — same base pattern as
    subject_roster.py::list_assessment_roster."""
    term = await db.get(AcademicTerm, academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic term not found.")

    active_ids = list((await db.scalars(
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
    te_by_student = dict((await db.execute(
        select(TermEnrollment.student_id, TermEnrollment.id).where(
            TermEnrollment.student_id.in_(active_ids),
            TermEnrollment.academic_term_id == academic_term_id,
            TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
        )
    )).all())
    return term, active_ids, te_by_student


async def get_subject_roster(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRosterStudent]:
    await _class_subject(class_id, subject_id, school_id, db)
    _term, active_ids, te_by_student = await _roster_base(class_id, academic_term_id, school_id, db)
    if not active_ids:
        return []

    te_ids = list(te_by_student.values())
    reg_by_te: dict[uuid.UUID, SubjectRegistration] = {}
    if te_ids:
        regs = await db.scalars(
            select(SubjectRegistration).where(
                SubjectRegistration.term_enrollment_id.in_(te_ids),
                SubjectRegistration.subject_id == subject_id,
            )
        )
        reg_by_te = {r.term_enrollment_id: r for r in regs}

    students = (await db.scalars(
        select(Student)
        .where(Student.id.in_(active_ids), Student.school_id == school_id)
        .order_by(Student.last_name, Student.first_name)
    )).all()

    # Removing a registration never deletes existing scores (Score has no FK
    # to SubjectRegistration) — but it does silently block future score edits
    # for that student/subject, since filter_eligible_for_subject only
    # accepts what's explicitly registered once any registration exists.
    # Surface has_scores so the UI can warn before an uncheck creates that trap.
    scored_ids: set[uuid.UUID] = set((await db.scalars(
        select(Score.student_id)
        .join(Assessment, Assessment.id == Score.assessment_id)
        .where(
            Score.student_id.in_(active_ids),
            Assessment.subject_id == subject_id,
            Assessment.academic_term_id == academic_term_id,
            Assessment.school_id == school_id,
        )
        .distinct()
    )).all())

    result = []
    for s in students:
        te_id = te_by_student.get(s.id)
        reg = reg_by_te.get(te_id) if te_id else None
        result.append(SubjectRosterStudent(
            student_id=s.id,
            display_name=_display_name(s.first_name, s.middle_name, s.last_name),
            admission_number=s.admission_number,
            enrolled=te_id is not None,
            is_registered=reg is not None,
            registration_id=reg.id if reg else None,
            has_scores=s.id in scored_ids,
        ))
    return result


async def set_subject_roster(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    req: SetSubjectRosterRequest,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> SetSubjectRosterResult:
    cs = await _class_subject(class_id, subject_id, school_id, db)
    _term, active_ids, te_by_student = await _roster_base(class_id, req.academic_term_id, school_id, db)

    te_ids = list(te_by_student.values())
    existing_regs: dict[uuid.UUID, SubjectRegistration] = {}
    if te_ids:
        rows = await db.scalars(
            select(SubjectRegistration).where(
                SubjectRegistration.term_enrollment_id.in_(te_ids),
                SubjectRegistration.subject_id == subject_id,
            )
        )
        existing_regs = {r.term_enrollment_id: r for r in rows}

    if req.expected_registered_ids is not None:
        currently_registered_ids = {
            student_id for student_id, te_id in te_by_student.items() if te_id in existing_regs
        }
        if set(req.expected_registered_ids) != currently_registered_ids:
            raise HTTPException(
                status_code=409,
                detail="This roster was changed by someone else since you loaded it. Refresh and try again.",
            )

    checked_ids = set(req.student_ids)
    registration_type = "ELECTIVE" if cs.is_elective else "CORE"
    item = [SubjectRegistrationItem(subject_id=subject_id, registration_type=registration_type)]

    registered = removed = skipped = 0
    for student_id in checked_ids:
        te_id = te_by_student.get(student_id)
        if te_id is None:
            skipped += 1
            continue
        if te_id not in existing_regs:
            await register_subjects(te_id, item, school_id, user_id, db, req.override_reason)
            registered += 1

    for student_id, te_id in te_by_student.items():
        if student_id not in checked_ids and te_id in existing_regs:
            await delete_subject_registration(
                te_id, existing_regs[te_id].id, school_id, user_id, db, req.override_reason,
            )
            removed += 1

    return SetSubjectRosterResult(registered=registered, removed=removed, skipped=skipped)
