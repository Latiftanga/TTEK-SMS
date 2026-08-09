"""Score entry/approval endpoints — split out of routers/assessments.py to stay under the 300-line cap."""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.scoring import BulkScoreSubmit, ScoreApproveRequest, ScoreRead
from app.services import scoring as score_svc

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("/{assessment_id}/scores", response_model=list[ScoreRead], status_code=201)
async def submit_scores(
    assessment_id: uuid.UUID,
    req: BulkScoreSubmit,
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await score_svc.submit_scores(assessment_id, req, school_id, user_id, db)


@router.get("/{assessment_id}/scores", response_model=list[ScoreRead])
async def list_scores(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await score_svc.list_scores(assessment_id, school_id, user_id, db)


@router.post("/{assessment_id}/scores/approve", response_model=list[ScoreRead])
async def approve_scores(
    assessment_id: uuid.UUID,
    req: ScoreApproveRequest,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await score_svc.approve_scores(assessment_id, req, school_id, user_id, db)
