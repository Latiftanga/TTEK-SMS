"""
Score entry, approval, and listing.

APPROVAL FLOW
-------------
1. Teacher calls submit_scores → Score rows upserted, is_approved=False,
   cached_grade_label cleared, ScoreAuditLog written for every change.
2. Approver/admin calls approve_scores → is_approved=True, cached_grade_label
   resolved from the school's default GradingScale, approved_by/at stamped.
3. If GradingScale bands change → grading.clear_cached_grades() clears labels
   so next approval recalculates from the new bands.

TERM LOCK
---------
AcademicTerm.results_locked freezes scoring for every assessment in that term,
independent of each Assessment's own is_published flag. A caller who holds
assessments.approve_scores can still push a change through by supplying a
non-blank override_reason, which is written to ScoreAuditLog.reason. Without
that permission + reason, a locked term rejects the write with 423.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override
from app.models.assessments import Assessment, Score, ScoreAuditLog
from app.models.students import Student
from app.schemas.assessments import BulkScoreSubmit, ScoreApproveRequest, ScoreRead
from app.services.grading import resolve_grade


def _to_read(s: Score) -> ScoreRead:
    return ScoreRead.model_validate(s)


async def submit_scores(
    assessment_id: uuid.UUID,
    req: BulkScoreSubmit,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[ScoreRead]:
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not assessment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    if assessment.is_published:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Cannot modify scores on a published assessment.",
        )
    override_reason = await check_term_lock_override(
        assessment.academic_term_id, req.override_reason, user_id, db
    )

    # Validate all scores before touching the DB
    for entry in req.scores:
        if entry.raw_score < 0 or entry.raw_score > assessment.max_score:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Score {entry.raw_score} out of range 0–{assessment.max_score}.",
            )

    # Batch-load existing scores to avoid N+1
    student_ids = [entry.student_id for entry in req.scores]
    existing_map: dict[str, Score] = {
        str(s.student_id): s
        for s in await db.scalars(
            select(Score).where(
                Score.assessment_id == assessment_id,
                Score.student_id.in_(student_ids),
            )
        )
    }

    now = datetime.now(timezone.utc)
    saved: list[Score] = []

    for entry in req.scores:
        existing = existing_map.get(str(entry.student_id))
        if existing:
            db.add(ScoreAuditLog(
                school_id=school_id, score_id=existing.id, changed_by_id=user_id,
                old_score=existing.raw_score, new_score=entry.raw_score, changed_at=now,
                reason=override_reason,
            ))
            existing.raw_score = entry.raw_score
            existing.is_approved = False
            existing.cached_grade_label = None
            existing.entered_by_id = user_id
            existing.submitted_at = now
            saved.append(existing)
        else:
            score = Score(
                school_id=school_id, assessment_id=assessment_id,
                student_id=entry.student_id, raw_score=entry.raw_score,
                entered_by_id=user_id, submitted_at=now,
            )
            db.add(score)
            await db.flush()
            db.add(ScoreAuditLog(
                school_id=school_id, score_id=score.id, changed_by_id=user_id,
                old_score=None, new_score=entry.raw_score, changed_at=now,
                reason=override_reason,
            ))
            saved.append(score)

    await db.flush()
    return [_to_read(s) for s in saved]


async def approve_scores(
    assessment_id: uuid.UUID,
    req: ScoreApproveRequest,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[ScoreRead]:
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not assessment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    if assessment.is_published:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Cannot approve scores on a published assessment.",
        )
    await check_term_lock_override(
        assessment.academic_term_id, req.override_reason, user_id, db
    )

    # Batch-load all requested scores at once
    scores = list(await db.scalars(
        select(Score).where(
            Score.id.in_(req.score_ids),
            Score.assessment_id == assessment_id,
            Score.school_id == school_id,
        )
    ))
    if len(scores) != len(req.score_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more scores not found.")

    now = datetime.now(timezone.utc)
    for score in scores:
        grade_label = await resolve_grade(score.raw_score, school_id, db)
        score.is_approved = True
        score.cached_grade_label = grade_label
        score.approved_by_id = user_id
        score.approved_at = now

    await db.flush()
    return [_to_read(s) for s in scores]


async def list_scores(
    assessment_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[ScoreRead]:
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not assessment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    rows = await db.scalars(
        select(Score)
        .join(Student, Student.id == Score.student_id)
        .where(Score.assessment_id == assessment_id, Score.school_id == school_id)
        .order_by(Student.last_name, Student.first_name)
    )
    return [_to_read(s) for s in rows]
