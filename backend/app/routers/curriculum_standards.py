"""
Curriculum standard router — minimal admin-facing CRUD (create/list/search/
retire), reusing the existing academic.* permission tier rather than
introducing a new one. See services/curriculum_standard.py.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.lesson_plans import CurriculumStandardCreate, CurriculumStandardRead
from app.services import curriculum_standard as cs_svc

router = APIRouter(prefix="/curriculum-standards", tags=["curriculum-standards"])


class _ActiveUpdate(BaseModel):
    is_active: bool


@router.post("", response_model=CurriculumStandardRead, status_code=201)
async def create_curriculum_standard(
    req: CurriculumStandardCreate,
    ids=Depends(require_permission("academic", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await cs_svc.create_curriculum_standard(req, school_id, db)


@router.get("", response_model=list[CurriculumStandardRead])
async def list_curriculum_standards(
    subject_catalogue_id: uuid.UUID | None = Query(default=None),
    level: str | None = Query(default=None),
    year_group: int | None = Query(default=None),
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    ids=Depends(require_permission("academic", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await cs_svc.list_curriculum_standards(
        school_id, db, subject_catalogue_id=subject_catalogue_id, level=level,
        year_group=year_group, q=q, include_inactive=include_inactive,
    )


@router.patch("/{curriculum_standard_id}", response_model=CurriculumStandardRead)
async def set_curriculum_standard_active(
    curriculum_standard_id: uuid.UUID,
    req: _ActiveUpdate,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await cs_svc.set_curriculum_standard_active(curriculum_standard_id, req.is_active, school_id, db)
