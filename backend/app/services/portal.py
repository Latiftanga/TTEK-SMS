"""
Self-service queries for the parent/student portal.

Access control (student-only, active user) is enforced by
_require_portal_user in routers/portal.py before any of these run — nothing
here re-checks it, so these functions must never be called from outside that
router.

Report card PDF generation itself stays in routers/portal.py directly
(reuses services/report_card.py + services/pdf.py, the same pipeline the
staff-facing report card endpoint uses) — the functions here only cover
"who am I" and "what can I see", not the report content itself.
"""
from __future__ import annotations
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, AcademicYear
from app.models.assessments import Assessment
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.schemas.portal import PortalProfile, PortalTermEnrollmentRead
from app.services.student import _class_display, _display_name, _get_class_map


async def get_my_profile(student_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> PortalProfile:
    student = await db.get(Student, student_id)
    school = await db.get(School, school_id)
    class_map = await _get_class_map([student_id], db)
    class_info = class_map.get(student_id)
    return PortalProfile(
        student_id=student.id,
        admission_number=student.admission_number,
        display_name=_display_name(student.first_name, student.middle_name, student.last_name),
        current_class_name=_class_display(*class_info[:4]) if class_info else None,
        school_name=school.name if school else "School",
    )


async def is_report_published(
    student_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """A report is visible once at least one Assessment is published for the
    student's class in that term. Mirrors the report-card gate in
    services/assessment.py::publish_assessment — publishing is per-assessment,
    not per-class, so one published assessment is enough to unlock viewing
    (the report itself only ever shows scores from published assessments)."""
    term = await db.get(AcademicTerm, academic_term_id)
    if not term:
        return False
    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
        )
    )
    if not sca:
        return False
    count = await db.scalar(
        select(func.count())
        .select_from(Assessment)
        .where(
            Assessment.class_id == sca.class_id,
            Assessment.academic_term_id == academic_term_id,
            Assessment.school_id == school_id,
            Assessment.is_published.is_(True),
        )
    ) or 0
    return count > 0


async def list_my_term_enrollments(
    student_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> list[PortalTermEnrollmentRead]:
    rows = (await db.execute(
        select(TermEnrollment, AcademicTerm, AcademicYear)
        .join(AcademicTerm, AcademicTerm.id == TermEnrollment.academic_term_id)
        .join(AcademicYear, AcademicYear.id == AcademicTerm.academic_year_id)
        .where(TermEnrollment.student_id == student_id, TermEnrollment.school_id == school_id)
        .order_by(AcademicYear.start_date.desc(), AcademicTerm.term_number.desc())
    )).all()

    results = []
    for te, term, year in rows:
        published = await is_report_published(student_id, term.id, school_id, db)
        results.append(PortalTermEnrollmentRead(
            id=te.id,
            academic_term_id=term.id,
            term_name=term.name,
            academic_year_name=year.name,
            is_current=term.is_current,
            is_published=published,
        ))
    return results
