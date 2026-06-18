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
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import Assessment, Score, ScoreAuditLog
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

    now = datetime.now(timezone.utc)
    saved: list[Score] = []

    for entry in req.scores:
        if entry.raw_score < 0 or entry.raw_score > assessment.max_score:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Score {entry.raw_score} out of range 0–{assessment.max_score}.",
            )
        existing = await db.scalar(
            select(Score).where(
                Score.assessment_id == assessment_id,
                Score.student_id == entry.student_id,
            )
        )
        if existing:
            log = ScoreAuditLog(
                school_id=school_id,
                score_id=existing.id,
                changed_by_id=user_id,
                old_score=existing.raw_score,
                new_score=entry.raw_score,
                changed_at=now,
            )
            db.add(log)
            existing.raw_score = entry.raw_score
            existing.is_approved = False
            existing.cached_grade_label = None
            existing.entered_by_id = user_id
            existing.submitted_at = now
            saved.append(existing)
        else:
            score = Score(
                school_id=school_id,
                assessment_id=assessment_id,
                student_id=entry.student_id,
                raw_score=entry.raw_score,
                entered_by_id=user_id,
                submitted_at=now,
            )
            db.add(score)
            await db.flush()
            log = ScoreAuditLog(
                school_id=school_id,
                score_id=score.id,
                changed_by_id=user_id,
                old_score=None,
                new_score=entry.raw_score,
                changed_at=now,
            )
            db.add(log)
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
    now = datetime.now(timezone.utc)
    approved: list[Score] = []

    for score_id in req.score_ids:
        score = await db.scalar(
            select(Score).where(
                Score.id == score_id,
                Score.assessment_id == assessment_id,
                Score.school_id == school_id,
            )
        )
        if not score:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Score {score_id} not found."
            )
        grade_label = await resolve_grade(score.raw_score, school_id, db)
        score.is_approved = True
        score.cached_grade_label = grade_label
        score.approved_by_id = user_id
        score.approved_at = now
        approved.append(score)

    await db.flush()
    return [_to_read(s) for s in approved]


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
        .where(Score.assessment_id == assessment_id, Score.school_id == school_id)
        .order_by(Score.submitted_at)
    )
    return [_to_read(s) for s in rows]
