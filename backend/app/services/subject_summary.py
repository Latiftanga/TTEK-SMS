"""
Subject-level summary — "how many students are doing English", "which
classes teaching Math have no teacher assigned" — aggregated across every
class in the school that offers a subject.

Everywhere else in this codebase, ClassSubject/SubjectTeacher/
SubjectRegistration are only ever queried starting from one class_id at a
time (assign a subject to THIS class, register students for THIS class's
subject roster, etc.). This is the one place that queries in the other
direction: given a subject_id, across every class that offers it. Purely
read-only — teacher assignment and student registration still only ever
happen on the class detail page (classes/[id]/SubjectsTab.svelte,
SubjectRosterPanel.svelte); this just surfaces the numbers and links back
into that existing page rather than duplicating its controls.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassSubject, SHSProgramme, Subject, SubjectTeacher
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment
from app.schemas.academic import SubjectClassSummary, SubjectSummary
from app.services.staff import _display_name as _staff_display_name
from app.services.student_display import _class_display_name


async def get_subject_summary(
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> SubjectSummary:
    subject = await db.scalar(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    term = await db.get(AcademicTerm, academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic term not found.")
    academic_year_id = term.academic_year_id

    class_rows = (await db.execute(
        select(Class, SHSProgramme.name)
        .join(ClassSubject, ClassSubject.class_id == Class.id)
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(
            ClassSubject.subject_id == subject_id,
            ClassSubject.school_id == school_id,
            ClassSubject.is_active.is_(True),
        )
        .order_by(Class.level, Class.year_group, Class.stream)
    )).all()
    if not class_rows:
        return SubjectSummary(
            subject_id=subject.id, subject_name=subject.name,
            total_classes=0, classes_without_teacher=0, total_students_registered=0, classes=[],
        )
    class_ids = [cls.id for cls, _prog in class_rows]

    teacher_by_class: dict[uuid.UUID, str] = {}
    teacher_rows = (await db.execute(
        select(SubjectTeacher.class_id, StaffMember.first_name, StaffMember.middle_name, StaffMember.last_name)
        .join(StaffMember, StaffMember.id == SubjectTeacher.staff_member_id)
        .where(
            SubjectTeacher.subject_id == subject_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.school_id == school_id,
            SubjectTeacher.is_active.is_(True),
            SubjectTeacher.class_id.in_(class_ids),
        )
    )).all()
    for class_id, first, middle, last in teacher_rows:
        teacher_by_class[class_id] = _staff_display_name(first, middle, last)

    registered_by_class: dict[uuid.UUID, int] = dict((await db.execute(
        select(StudentClassAssignment.class_id, func.count(SubjectRegistration.id))
        .select_from(SubjectRegistration)
        .join(TermEnrollment, TermEnrollment.id == SubjectRegistration.term_enrollment_id)
        .join(StudentClassAssignment, StudentClassAssignment.student_id == TermEnrollment.student_id)
        .join(Student, Student.id == TermEnrollment.student_id)
        .where(
            SubjectRegistration.subject_id == subject_id,
            SubjectRegistration.school_id == school_id,
            TermEnrollment.academic_term_id == academic_term_id,
            TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
            StudentClassAssignment.academic_year_id == academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
            StudentClassAssignment.class_id.in_(class_ids),
            Student.is_active.is_(True),
        )
        .group_by(StudentClassAssignment.class_id)
    )).all())

    classes = [
        SubjectClassSummary(
            class_id=cls.id,
            display_name=_class_display_name(cls.level, cls.year_group, prog_name, cls.stream),
            teacher_name=teacher_by_class.get(cls.id),
            registered_count=registered_by_class.get(cls.id, 0),
        )
        for cls, prog_name in class_rows
    ]

    return SubjectSummary(
        subject_id=subject.id,
        subject_name=subject.name,
        total_classes=len(classes),
        classes_without_teacher=sum(1 for c in classes if c.teacher_name is None),
        total_students_registered=sum(c.registered_count for c in classes),
        classes=classes,
    )
