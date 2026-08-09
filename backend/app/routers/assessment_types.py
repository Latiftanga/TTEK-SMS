"""Assessment type + preset endpoints — split out of routers/assessments.py to stay under the 300-line cap."""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.assessment_type import AssessmentTypeCreate, AssessmentTypeRead, AssessmentTypeUpdate
from app.services import assessment_type as atype_svc
from app.services.assessment_type_presets import TYPE_PRESETS

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("/types", response_model=AssessmentTypeRead, status_code=201)
async def create_assessment_type(
    req: AssessmentTypeCreate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await atype_svc.create_assessment_type(req, school_id, db)


@router.get("/types", response_model=list[AssessmentTypeRead])
async def list_assessment_types(
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await atype_svc.list_assessment_types(school_id, db)


@router.patch("/types/{type_id}", response_model=AssessmentTypeRead)
async def update_assessment_type(
    type_id: uuid.UUID,
    req: AssessmentTypeUpdate,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await atype_svc.update_assessment_type(type_id, req, school_id, db)


@router.get("/type-presets", response_model=dict[str, list[AssessmentTypeCreate]])
async def get_type_presets(
    ids=Depends(require_permission("assessments", "approve_scores")),
):
    # Same permission gate as the /types endpoints this pre-fills — read-only
    # static config, no school_id/db access needed at all.
    return TYPE_PRESETS
