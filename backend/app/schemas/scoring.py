from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ScoreSubmit(BaseModel):
    student_id: uuid.UUID
    raw_score: Decimal


class BulkScoreSubmit(BaseModel):
    scores: list[ScoreSubmit]
    # Only used/required when the assessment's term has results_locked=True.
    # Honoured only if the caller holds assessments.approve_scores.
    override_reason: str | None = None


class ScoreRead(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    raw_score: Decimal
    cached_grade_label: str | None
    is_approved: bool
    entered_by_id: uuid.UUID
    approved_by_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    model_config = {"from_attributes": True}


class ScoreApproveRequest(BaseModel):
    score_ids: list[uuid.UUID]
    # Only required when the assessment's term has results_locked=True.
    override_reason: str | None = None
