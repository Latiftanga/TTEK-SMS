"""
Full-history transcript — every term a student has ever been enrolled in,
grouped by academic year, spanning active/withdrawn/graduated students alike.

Unlike report_card.py::assemble() (one TermEnrollment at a time), this batches
across every term the student has so the query count stays constant (~6)
regardless of how many terms are in their history — the same shape as
report_card.py::_load_scores(), just widened from `== term_id` to
`.in_(term_ids)` and grouped by term in Python afterward. Attendance uses the
shared services/attendance_stats.py::compute_attendance_stats(), which is
already built around a term_ids list — a direct fit, no batching needed here.

Deliberately omits per-term class rank (report_card_rank.py::compute_rank is
an expensive per-class query; calling it once per term would reintroduce the
exact N+1 explosion this batching avoids) and any QR/verify token (the
existing scheme verifies one TermEnrollment at a time — a transcript spans
many; each underlying report card stays individually QR-verifiable as today).
"""
from __future__ import annotations
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.student_scope import assert_can_view_student
from app.models.academic import AcademicTerm, AcademicYear, Class, SHSProgramme, Subject
from app.models.assessments import Assessment, AssessmentType, Score, StudentBehaviourRecord
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.services.attendance_stats import compute_attendance_stats
from app.services.grading import get_default_scale_with_bands, grade_legend_rows
from app.services.report_card_scoring import _compute_weighted_scores
from app.services.student_display import _photo_url


def _class_name(cls: Class, programme_name: str | None) -> str:
    parts = [cls.level, str(cls.year_group)]
    if programme_name:
        parts.append(programme_name)
    if cls.stream:
        parts.append(cls.stream)
    return " ".join(parts)


async def assemble_transcript(
    student_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> dict:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    # Same "can this caller view this student" boundary as the rest of the
    # Students module (core/student_scope.py) — assessments.view alone (the
    # permission gating this route) doesn't imply cross-class visibility; a
    # scoped caller must actually be this student's ClassTeacher/SubjectTeacher/
    # HouseMaster (of their *current* class) or hold one of the broad-access
    # permissions resolve_student_view_scope() recognizes.
    await assert_can_view_student(user_id, student_id, school_id, db)
    school = await db.get(School, school_id)

    term_rows = (await db.execute(
        select(TermEnrollment, AcademicTerm, AcademicYear)
        .join(AcademicTerm, AcademicTerm.id == TermEnrollment.academic_term_id)
        .join(AcademicYear, AcademicYear.id == AcademicTerm.academic_year_id)
        .where(TermEnrollment.student_id == student_id, TermEnrollment.school_id == school_id)
        .order_by(AcademicYear.start_date, AcademicTerm.term_number)
    )).all()

    scale = await get_default_scale_with_bands(school_id, db)

    if not term_rows:
        return {
            "student_name": f"{student.first_name} {student.last_name}",
            "admission_number": student.admission_number,
            "school_name": school.name if school else "",
            "school_phone": school.phone if school else None,
            "school_email": school.email if school else None,
            "school_address": school.address if school else None,
            "logo_url": f"/uploads/{school.logo_path}" if school and school.logo_path else None,
            "photo_url": _photo_url(student.photo_path),
            "grade_legend": grade_legend_rows(scale),
            "years": [],
        }

    term_ids = [te.academic_term_id for te, _, _ in term_rows]
    year_ids = {t.academic_year_id for _, t, _ in term_rows}

    # Class assignment per academic year — one query, keyed by academic_year_id.
    sca_rows = (await db.execute(
        select(StudentClassAssignment, Class, SHSProgramme.name)
        .join(Class, Class.id == StudentClassAssignment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(
            StudentClassAssignment.student_id == student_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.academic_year_id.in_(year_ids),
        )
    )).all()
    class_by_year: dict[uuid.UUID, str] = {
        sca.academic_year_id: _class_name(cls, prog_name)
        for sca, cls, prog_name in sca_rows
    }

    # Scores for every term in one query, grouped by term_id in Python.
    score_rows = (await db.execute(
        select(
            Assessment.academic_term_id,
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
            Assessment.academic_term_id.in_(term_ids),
            Assessment.is_published.is_(True),
        )
    )).mappings().all()
    scores_by_term: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for row in score_rows:
        d = dict(row)
        scores_by_term[d.pop("academic_term_id")].append(d)

    # Attendance for every term in one grouped query (shared with report_card.py
    # so both use the exact same present/total definition).
    attendance_by_term = await compute_attendance_stats(student_id, term_ids, school_id, db)

    # Behaviour records for every term in one query, grouped by term_id in Python.
    behaviour_rows = (await db.scalars(
        select(StudentBehaviourRecord)
        .where(
            StudentBehaviourRecord.student_id == student_id,
            StudentBehaviourRecord.school_id == school_id,
            StudentBehaviourRecord.academic_term_id.in_(term_ids),
        )
        .order_by(StudentBehaviourRecord.incident_date)
    )).all()
    behaviour_by_term: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for b in behaviour_rows:
        behaviour_by_term[b.academic_term_id].append({
            "incident_type": b.incident_type,
            "severity": b.severity,
            "incident_date": str(b.incident_date),
            "description": b.description,
        })

    years: dict[uuid.UUID, dict] = {}
    for te, term, year in term_rows:
        subject_weighted = _compute_weighted_scores(scores_by_term.get(term.id, []))
        total_score = sum(subject_weighted.values()) if subject_weighted else Decimal("0")
        max_possible = Decimal("100") * len(subject_weighted) if subject_weighted else Decimal("0")
        present, total_days = attendance_by_term.get(term.id, (0, 0))

        year_bucket = years.setdefault(year.id, {"academic_year_name": year.name, "terms": []})
        year_bucket["terms"].append({
            "term_name": term.name,
            "class_name": class_by_year.get(year.id),
            "scores": scores_by_term.get(term.id, []),
            "subject_weighted": subject_weighted,
            "total_score": total_score,
            "max_possible": max_possible,
            "days_present": present,
            "total_school_days": total_days,
            "behaviour_records": behaviour_by_term.get(term.id, []),
        })

    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "admission_number": student.admission_number,
        "school_name": school.name if school else "",
        "school_phone": school.phone if school else None,
        "school_email": school.email if school else None,
        "school_address": school.address if school else None,
        "logo_url": f"/uploads/{school.logo_path}" if school and school.logo_path else None,
        "photo_url": _photo_url(student.photo_path),
        "grade_legend": grade_legend_rows(scale),
        "years": list(years.values()),
    }
