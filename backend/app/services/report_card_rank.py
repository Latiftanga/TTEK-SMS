"""
Class ranking for report cards — split out of report_card.py (was over the
300-line cap).
"""
from __future__ import annotations
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.students import SubjectRegistration
from app.services.report_card_scoring import _compute_weighted_scores


async def compute_rank(
    student_id: uuid.UUID, class_id: uuid.UUID, term_id: uuid.UUID,
    academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> tuple[int, int]:
    """Returns (rank, class_size). Rank 1 = highest weighted total.

    ELECTIVE-AWARE RANKING
    -----------------------
    A class can split by elective (SHS), so summing every subject a student
    happens to have scores for isn't a fair comparison — one student's total
    might include an easy elective, another's a hard one. If a student's
    TermEnrollment has any SubjectRegistration rows recorded, only CORE-
    registered subjects count toward their rank total; electives still show
    on the report card, they just don't feed the single class-position number.

    Backward compatible by design: a TermEnrollment with zero registration
    rows (the common case for a school that never uses subject registration —
    GES Basic, no electives) falls back to today's behaviour of summing every
    subject with a score, exactly as before.
    """
    q = text("""
        SELECT sca.student_id,
               te.id AS term_enrollment_id,
               sc.raw_score,
               a.max_score,
               at.weight,
               at.aggregation_strategy,
               a.subject_id,
               sub.name AS subject_name,
               at.name  AS type_name,
               at.code  AS type_code,
               sr.registration_type
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
        -- category != 'DIAGNOSTIC' lives on this join's own ON clause, not a
        -- WHERE filter — a WHERE would also drop students with zero scores
        -- at all (their `at.*` columns are already NULL from the LEFT JOIN),
        -- breaking the "count every student, even with nothing recorded"
        -- requirement below. A diagnostic assessment's `at.weight` comes
        -- through NULL instead, and the existing `not r.weight` check two
        -- blocks down already excludes it — no new Python logic needed.
        LEFT JOIN assessment_type at ON at.id = a.assessment_type_id
            AND at.category != 'DIAGNOSTIC'
        LEFT JOIN subject sub ON sub.id = a.subject_id
        LEFT JOIN subject_registration sr
            ON sr.term_enrollment_id = te.id
           AND sr.subject_id = a.subject_id
        WHERE sca.class_id = :class_id
          AND sca.academic_year_id = :academic_year_id
          AND sca.is_active = true
          AND te.is_active = true
    """)
    rows = (await db.execute(q, {
        "school_id": str(school_id),
        "term_id": str(term_id),
        "class_id": str(class_id),
        "academic_year_id": str(academic_year_id),
    })).all()

    te_ids = {r.term_enrollment_id for r in rows}
    registered_te_ids: set[uuid.UUID] = set(
        (await db.scalars(
            select(SubjectRegistration.term_enrollment_id)
            .where(SubjectRegistration.term_enrollment_id.in_(te_ids))
            .distinct()
        )).all()
    ) if te_ids else set()

    student_score_rows: dict[str, list[dict]] = defaultdict(list)
    students_seen: set[str] = set()
    for r in rows:
        sid = str(r.student_id)
        students_seen.add(sid)
        if r.raw_score is None or not r.max_score or not r.weight:
            continue
        # Registration data, when present for this TermEnrollment, is
        # authoritative — only CORE subjects count. Its absence falls back
        # to including every subject (today's behaviour).
        if r.term_enrollment_id in registered_te_ids and r.registration_type != "CORE":
            continue
        student_score_rows[sid].append({
            "raw_score": r.raw_score, "max_score": r.max_score,
            "type_weight": r.weight,
            "type_aggregation_strategy": r.aggregation_strategy,
            "subject_name": r.subject_name or "",
            "type_name": r.type_name or "",
            "type_code": r.type_code or "",
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
