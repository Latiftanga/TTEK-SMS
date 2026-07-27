"""
Report card data assembly.

assemble() fetches all data for one TermEnrollment and returns a context dict
ready for Jinja2. No PDF logic here — see services/pdf.py.

Weighted-score aggregation lives in report_card_scoring.py; class ranking
lives in report_card_rank.py — both split out when this file went over the
300-line cap.
"""
from __future__ import annotations
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher, Subject
from app.models.assessments import Assessment, AssessmentType, Score, StudentBehaviourRecord
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.services.attendance_stats import compute_attendance_stats
from app.services.qr import generate_qr_image, generate_token
from app.services.report_card_rank import compute_rank
from app.services.report_card_scoring import _compute_weighted_scores


def _class_name(cls: Class, programme_name: str | None) -> str:
    parts = [cls.level, str(cls.year_group)]
    if programme_name:
        parts.append(programme_name)
    if cls.stream:
        parts.append(cls.stream)
    return " ".join(parts)


async def _load_scores(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    rows = (await db.execute(
        select(
            Score.raw_score,
            Score.cached_grade_label,
            Assessment.max_score,
            AssessmentType.name.label("type_name"),
            AssessmentType.weight.label("type_weight"),
            Subject.name.label("subject_name"),
        )
        .join(Assessment, Assessment.id == Score.assessment_id)
        .join(AssessmentType, AssessmentType.id == Assessment.assessment_type_id)
        .join(Subject, Subject.id == Assessment.subject_id)
        .where(
            Score.student_id == student_id,
            Score.school_id == school_id,
            Score.is_approved.is_(True),
            Assessment.academic_term_id == term_id,
            Assessment.is_published.is_(True),
        )
        .order_by(Subject.name, AssessmentType.name)
    )).mappings().all()
    return [dict(r) for r in rows]


async def assemble(
    enrollment_id: uuid.UUID, school_id: uuid.UUID, format: str, db: AsyncSession
) -> dict:
    """Build the full context dict for the Jinja2 report card template."""
    te = await db.scalar(
        select(TermEnrollment)
        .where(TermEnrollment.id == enrollment_id, TermEnrollment.school_id == school_id)
        .options(selectinload(TermEnrollment.student))
    )
    if not te:
        raise HTTPException(404, "Term enrollment not found.")

    term = await db.scalar(
        select(AcademicTerm)
        .where(AcademicTerm.id == te.academic_term_id)
        .options(selectinload(AcademicTerm.academic_year))
    )
    school = await db.get(School, school_id)

    # Resolve class from StudentClassAssignment (the authoritative class membership)
    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == te.student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
        )
    )
    cls = await db.get(Class, sca.class_id) if sca else None
    if not cls:
        raise HTTPException(404, "Student has no class assignment for this academic year.")

    # Programme name for class label
    programme_name: str | None = None
    if cls.programme_id:
        from app.models.academic import SHSProgramme
        prog = await db.get(SHSProgramme, cls.programme_id)
        programme_name = prog.name if prog else None

    # Class teacher — ClassTeacher is a yearly assignment, not per-term
    ct = await db.scalar(
        select(ClassTeacher)
        .where(
            ClassTeacher.class_id == cls.id,
            ClassTeacher.academic_year_id == term.academic_year_id,
            ClassTeacher.is_active.is_(True),
        )
    )
    teacher_name: str | None = None
    if ct:
        sm = await db.get(StaffMember, ct.staff_member_id)
        teacher_name = f"{sm.first_name} {sm.last_name}" if sm else None

    scores = await _load_scores(te.student_id, te.academic_term_id, school_id, db)
    attendance_stats = await compute_attendance_stats(
        te.student_id, [te.academic_term_id], school_id, db
    )
    days_present, total_days = attendance_stats.get(te.academic_term_id, (0, 0))
    rank, class_size = await compute_rank(
        te.student_id, cls.id, te.academic_term_id, term.academic_year_id, school_id, db
    )

    behaviour = (await db.scalars(
        select(StudentBehaviourRecord)
        .where(
            StudentBehaviourRecord.student_id == te.student_id,
            StudentBehaviourRecord.academic_term_id == te.academic_term_id,
            StudentBehaviourRecord.school_id == school_id,
        )
        .order_by(StudentBehaviourRecord.incident_date)
    )).all()

    subject_weighted = _compute_weighted_scores(scores)
    total_score = sum(subject_weighted.values())
    max_possible = Decimal("100") * len(subject_weighted) if subject_weighted else Decimal("0")
    student = te.student

    logo_url: str | None = None
    if school.logo_path:
        logo_url = f"/uploads/{school.logo_path}"

    qr_token = generate_token(enrollment_id, school_id)

    return {
        "enrollment_id": str(enrollment_id),
        "student_name": f"{student.first_name} {student.last_name}",
        "admission_number": student.admission_number,
        "class_name": _class_name(cls, programme_name),
        "term_name": term.name,
        "academic_year_name": term.academic_year.name,
        "class_teacher_name": teacher_name,
        "school_name": school.name,
        "logo_url": logo_url,
        "scores": scores,
        "subject_weighted": subject_weighted,
        "total_score": total_score,
        "max_possible": max_possible,
        "rank": rank,
        "class_size": class_size,
        "days_present": days_present,
        "total_school_days": total_days,
        "behaviour_records": [
            {
                "incident_type": b.incident_type,
                "severity": b.severity,
                "incident_date": str(b.incident_date),
                "description": b.description,
            }
            for b in behaviour
        ],
        "qr_token": qr_token,
        "qr_image": generate_qr_image(qr_token),
        "format": format,
    }
