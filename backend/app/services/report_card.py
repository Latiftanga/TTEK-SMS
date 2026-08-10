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

from app.core.teacher_scope import resolve_report_card_scope
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher, Subject
from app.models.assessments import (
    Assessment, AssessmentCategory, AssessmentType, GradingScale, Score, StudentBehaviourRecord,
)
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.schemas.school import _logo_url
from app.services.attendance_stats import compute_attendance_stats
from app.services.class_progression import level_rank
from app.services.grading import get_default_scale_with_bands, grade_legend_rows, resolve_grade_from_scale
from app.services.qr import generate_qr_image, generate_token
from app.services.report_card_rank import compute_rank
from app.services.report_card_scoring import _compute_type_breakdown, _compute_weighted_scores
from app.services.student_display import _photo_url


def _class_name(cls: Class, programme_name: str | None) -> str:
    parts = [cls.level, str(cls.year_group)]
    if programme_name:
        parts.append(programme_name)
    if cls.stream:
        parts.append(cls.stream)
    return " ".join(parts)


def _group_by_subject(
    scores: list[dict], subject_weighted: dict[str, Decimal],
    type_breakdown: dict[str, dict[str, Decimal]], scale: GradingScale | None,
) -> list[dict]:
    """Fold the flat per-assessment `scores` rows (already ordered by
    Subject.name — see _load_scores) into one block per subject: its
    category rows (`rows` — still needed by the early-years milestone
    section), its per-type-code resolved values (`type_values` — what the
    numeric section's unified table actually renders per column), its
    weighted total (report_card_scoring.py::_compute_weighted_scores), and a
    letter grade resolved for that total. This — not the flat `scores` list
    — is what the report card template renders; `scores`/`subject_weighted`
    stay in the context unchanged since total_score/rank still depend on them."""
    groups: list[dict] = []
    by_subject: dict[str, dict] = {}
    for row in scores:
        subj = row["subject_name"]
        group = by_subject.get(subj)
        if group is None:
            total = subject_weighted.get(subj, Decimal("0"))
            group = {
                "subject_name": subj,
                "rows": [],
                "total": total,
                "grade": resolve_grade_from_scale(total, scale),
                "type_values": type_breakdown.get(subj, {}),
            }
            by_subject[subj] = group
            groups.append(group)
        group["rows"].append(row)
    return groups


def _type_columns(scores: list[dict]) -> list[dict]:
    """Distinct assessment-type codes referenced anywhere in this report,
    ordered heaviest-weight-first (then code) — the fixed set of columns the
    numeric section's unified subject table renders. Not every subject
    necessarily has an entry for every column (a subject that never used a
    given type renders "—" there — see the template)."""
    seen: dict[str, dict] = {}
    for row in scores:
        code = row["type_code"]
        if code not in seen:
            seen[code] = {"code": code, "name": row["type_name"], "weight": row["type_weight"]}
    return sorted(seen.values(), key=lambda c: (-c["weight"], c["code"]))


async def _load_scores(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """Diagnostic-category types are excluded here at the query level — per
    the aggregation engine's hard rule, they never enter term aggregation or
    report-card output at all, individually or in a total (services/
    aggregation.py)."""
    rows = (await db.execute(
        select(
            Score.raw_score,
            Assessment.max_score,
            AssessmentType.name.label("type_name"),
            AssessmentType.code.label("type_code"),
            AssessmentType.weight.label("type_weight"),
            AssessmentType.aggregation_strategy.label("type_aggregation_strategy"),
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
            AssessmentType.category != AssessmentCategory.DIAGNOSTIC,
        )
        .order_by(Subject.name, AssessmentType.name)
    )).mappings().all()
    return [dict(r) for r in rows]


async def assemble(
    enrollment_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
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

    # Creche/Nursery/KG get the milestone-style section instead of numeric
    # scores/rank — auto-detected from the class-level ladder already used
    # for promotion validity, not a manual per-request choice.
    is_early_years = 0 <= level_rank(cls.level or "") < level_rank("Basic")

    scope = await resolve_report_card_scope(user_id, term.academic_year_id, db)
    if scope is not None and cls.id not in scope:
        raise HTTPException(404, "Term enrollment not found.")

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

    logo_url = _logo_url(school.logo_path)

    qr_token = generate_token(enrollment_id, school_id)
    scale = await get_default_scale_with_bands(school_id, db)
    type_breakdown = _compute_type_breakdown(scores)
    type_columns = _type_columns(scores)
    subject_groups = _group_by_subject(scores, subject_weighted, type_breakdown, scale)

    return {
        "enrollment_id": str(enrollment_id),
        "student_name": f"{student.first_name} {student.last_name}",
        "admission_number": student.admission_number,
        "class_name": _class_name(cls, programme_name),
        "term_name": term.name,
        "academic_year_name": term.academic_year.name,
        "class_teacher_name": teacher_name,
        "school_name": school.name,
        "school_phone": school.phone,
        "school_email": school.email,
        "school_address": school.address,
        "brand_color": school.brand_color,
        "logo_url": logo_url,
        "photo_url": _photo_url(student.photo_path),
        "is_early_years": is_early_years,
        "grade_legend": grade_legend_rows(scale),
        "type_columns": type_columns,
        "subject_groups": subject_groups,
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
    }
