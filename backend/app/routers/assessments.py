"""
Assessments router — grading scales, assessment types, assessments, scores.

Permission map:
  assessments.approve_scores → grading scale management, assessment type CRUD,
                               assessment create/publish, score approval
  assessments.enter_scores   → submit scores for an assessment
  assessments.view           → read-only access to everything
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.schemas.assessments import (
    AssessmentCreate, AssessmentRead,
    AssessmentTypeCreate, AssessmentTypeRead, AssessmentTypeUpdate,
    BulkScoreSubmit, GradeCreate, GradeRead,
    GradingScaleCreate, GradingScaleRead, GradingScaleUpdate,
    ScoreApproveRequest, ScoreRead,
)
from app.services import assessment as assess_svc
from app.services import grading as grade_svc
from app.services import scoring as score_svc

router = APIRouter(prefix="/assessments", tags=["assessments"])


# ── Grading scales ────────────────────────────────────────────────────────────

@router.post("/grading-scales", response_model=GradingScaleRead, status_code=201)
async def create_grading_scale(
    req: GradingScaleCreate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return GradingScaleRead.model_validate(
        await grade_svc.create_grading_scale(req, school_id, db)
    )


@router.get("/grading-scales", response_model=list[GradingScaleRead])
async def list_grading_scales(
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return [
        GradingScaleRead.model_validate(s)
        for s in await grade_svc.list_grading_scales(school_id, db)
    ]


@router.get("/grading-scales/{scale_id}", response_model=GradingScaleRead)
async def get_grading_scale(
    scale_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return GradingScaleRead.model_validate(
        await grade_svc.get_grading_scale(scale_id, school_id, db)
    )


@router.patch("/grading-scales/{scale_id}", response_model=GradingScaleRead)
async def update_grading_scale(
    scale_id: uuid.UUID,
    req: GradingScaleUpdate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return GradingScaleRead.model_validate(
        await grade_svc.update_grading_scale(scale_id, req, school_id, db)
    )


@router.post("/grading-scales/{scale_id}/grades", response_model=GradeRead, status_code=201)
async def add_grade(
    scale_id: uuid.UUID,
    req: GradeCreate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return GradeRead.model_validate(
        await grade_svc.add_grade(scale_id, req, school_id, db)
    )


@router.delete("/grading-scales/{scale_id}/grades/{grade_id}", status_code=204)
async def delete_grade(
    scale_id: uuid.UUID,
    grade_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await grade_svc.delete_grade(scale_id, grade_id, school_id, db)


# ── Assessment types ──────────────────────────────────────────────────────────

@router.post("/types", response_model=AssessmentTypeRead, status_code=201)
async def create_assessment_type(
    req: AssessmentTypeCreate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.create_assessment_type(req, school_id, db)


@router.get("/types", response_model=list[AssessmentTypeRead])
async def list_assessment_types(
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.list_assessment_types(school_id, db)


@router.patch("/types/{type_id}", response_model=AssessmentTypeRead)
async def update_assessment_type(
    type_id: uuid.UUID,
    req: AssessmentTypeUpdate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.update_assessment_type(type_id, req, school_id, db)


# ── Assessments ───────────────────────────────────────────────────────────────

@router.post("", response_model=AssessmentRead, status_code=201)
async def create_assessment(
    req: AssessmentCreate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.create_assessment(req, school_id, db)


@router.get("", response_model=list[AssessmentRead])
async def list_assessments(
    class_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.list_assessments(class_id, term_id, school_id, db)


@router.get("/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.get_assessment(assessment_id, school_id, db)


@router.post("/{assessment_id}/publish", response_model=AssessmentRead)
async def publish_assessment(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await assess_svc.publish_assessment(assessment_id, school_id, db)


# ── Scores ────────────────────────────────────────────────────────────────────

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
    _, school_id = ids
    return await score_svc.list_scores(assessment_id, school_id, db)


@router.post("/{assessment_id}/scores/approve", response_model=list[ScoreRead])
async def approve_scores(
    assessment_id: uuid.UUID,
    req: ScoreApproveRequest,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await score_svc.approve_scores(assessment_id, req, school_id, user_id, db)
