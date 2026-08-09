"""Grading scale endpoints — split out of routers/assessments.py to stay under the 300-line cap."""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.grading import GradeCreate, GradeRead, GradingScaleCreate, GradingScaleRead, GradingScaleUpdate
from app.services import grading as grade_svc

router = APIRouter(prefix="/assessments", tags=["assessments"])


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
