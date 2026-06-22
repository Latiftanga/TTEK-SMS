"""
Report card data assembly.

assemble() fetches all data for one TermEnrollment and returns a context dict
ready for Jinja2. No PDF logic here — see services/pdf.py.
"""
from __future__ import annotations
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher, Subject
from app.models.assessments import Assessment, AssessmentType, Score, StudentBehaviourRecord
from app.models.attendance import AttendanceRecord, SchoolCalendar
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.services.qr import generate_token


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


def _compute_weighted_scores(scores: list[dict]) -> dict[str, Decimal]:
    """
    For each subject, compute the weighted score out of 100.

    Per type: contribution = (sum_raw / sum_max) * type_weight
    Subject total = sum of contributions across all types.

    If weights don't sum to 100 the total is proportional — callers display
    whatever the school configured.
    """
    # Group by subject → type
    subjects: dict[str, dict[str, dict]] = {}
    for row in scores:
        subj = row["subject_name"]
        typ  = row["type_name"]
        if subj not in subjects:
            subjects[subj] = {}
        if typ not in subjects[subj]:
            subjects[subj][typ] = {
                "weight": Decimal(str(row["type_weight"])),
                "sum_raw": Decimal("0"),
                "sum_max": Decimal("0"),
            }
        subjects[subj][typ]["sum_raw"] += Decimal(str(row["raw_score"]))
        subjects[subj][typ]["sum_max"] += Decimal(str(row["max_score"]))

    result: dict[str, Decimal] = {}
    for subj, types in subjects.items():
        total = Decimal("0")
        for t in types.values():
            if t["sum_max"] > 0:
                total += (t["sum_raw"] / t["sum_max"]) * t["weight"]
        result[subj] = total.quantize(Decimal("0.01"))
    return result


async def _load_attendance(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> tuple[int, int]:
    """Returns (days_present, total_school_days)."""
    total = await db.scalar(
        select(func.count())
        .select_from(AttendanceRecord)
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
        )
    ) or 0
    present = await db.scalar(
        select(func.count())
        .select_from(AttendanceRecord)
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            AttendanceRecord.status == "PRESENT",
        )
    ) or 0
    return present, total


async def _compute_rank(
    student_id: uuid.UUID, class_id: uuid.UUID, term_id: uuid.UUID,
    academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> tuple[int, int]:
    """Returns (rank, class_size). Rank 1 = highest weighted total."""
    q = text("""
        SELECT sca.student_id,
               sc.raw_score,
               a.max_score,
               at.weight,
               sub.name AS subject_name,
               at.name  AS type_name
        FROM student_class_assignment sca
        JOIN term_enrollment te
            ON te.student_id = sca.student_id
           AND te.academic_term_id = :term_id
        LEFT JOIN score sc ON sc.student_id = sca.student_id
            AND sc.school_id = :school_id
            AND sc.is_approved = true
        LEFT JOIN assessment a ON a.id = sc.assessment_id
            AND a.academic_term_id = :term_id
            AND a.is_published = true
        LEFT JOIN assessment_type at ON at.id = a.assessment_type_id
        LEFT JOIN subject sub ON sub.id = a.subject_id
        WHERE sca.class_id = :class_id
          AND sca.academic_year_id = :academic_year_id
    """)
    rows = (await db.execute(q, {
        "school_id": str(school_id),
        "term_id": str(term_id),
        "class_id": str(class_id),
        "academic_year_id": str(academic_year_id),
    })).all()

    from collections import defaultdict
    student_score_rows: dict[str, list[dict]] = defaultdict(list)
    students_seen: set[str] = set()
    for r in rows:
        sid = str(r.student_id)
        students_seen.add(sid)
        if r.raw_score is not None and r.max_score and r.weight:
            student_score_rows[sid].append({
                "raw_score": r.raw_score, "max_score": r.max_score,
                "type_weight": r.weight,
                "subject_name": r.subject_name or "",
                "type_name": r.type_name or "",
            })

    totals = {
        sid: sum(_compute_weighted_scores(score_rows).values())
        for sid, score_rows in student_score_rows.items()
    }
    for sid in students_seen:
        totals.setdefault(sid, Decimal("0"))

    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    class_size = len(ranked)
    rank = next(
        (i + 1 for i, (sid, _) in enumerate(ranked) if sid == str(student_id)),
        class_size,
    )
    return rank, class_size


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

    # Class teacher
    ct = await db.scalar(
        select(ClassTeacher)
        .where(
            ClassTeacher.class_id == cls.id,
            ClassTeacher.academic_term_id == te.academic_term_id,
            ClassTeacher.is_active.is_(True),
        )
    )
    teacher_name: str | None = None
    if ct:
        sm = await db.get(StaffMember, ct.staff_member_id)
        teacher_name = f"{sm.first_name} {sm.last_name}" if sm else None

    scores = await _load_scores(te.student_id, te.academic_term_id, school_id, db)
    days_present, total_days = await _load_attendance(
        te.student_id, te.academic_term_id, school_id, db
    )
    rank, class_size = await _compute_rank(
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
        "qr_token": generate_token(enrollment_id, school_id),
        "format": format,
    }
