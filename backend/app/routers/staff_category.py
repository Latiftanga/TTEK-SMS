"""Staff category and rank management endpoints.

GET  /staff/categories              — list categories visible to this school
POST /staff/categories              — create a school-specific custom category
GET  /staff/ranks?category_id=      — list ranks for a category
POST /staff/ranks                   — create a custom rank

Visibility by school ownership:
  PUBLIC  → GES templates (school_id=NULL) + own custom entries
  PRIVATE → own custom entries only
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.school import School, SchoolOwnership
from app.models.staff import StaffCategory, StaffRank
from app.schemas.staff import StaffCategoryCreate, StaffCategoryRead, StaffRankCreate, StaffRankRead

router = APIRouter(tags=["staff"])


@router.get("/staff/categories", response_model=list[StaffCategoryRead])
async def list_categories(
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    school = await db.get(School, school_id)
    if school and school.ownership == SchoolOwnership.PUBLIC:
        condition = or_(StaffCategory.school_id == school_id, StaffCategory.school_id.is_(None))
    else:
        condition = StaffCategory.school_id == school_id
    rows = await db.scalars(
        select(StaffCategory).where(condition, StaffCategory.is_active == True).order_by(StaffCategory.name)
    )
    return [StaffCategoryRead.model_validate(c) for c in rows]


@router.post("/staff/categories", response_model=StaffCategoryRead, status_code=201)
async def create_category(
    req: StaffCategoryCreate,
    ids=Depends(require_permission("staff", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    cat = StaffCategory(
        school_id=school_id,
        name=req.name.strip(),
        code=req.code.strip().upper(),
        staff_type=req.staff_type,
        is_template=False,
        is_active=True,
    )
    db.add(cat)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"A category with code '{req.code.upper()}' already exists for this school.",
        )
    return StaffCategoryRead.model_validate(cat)


@router.get("/staff/ranks", response_model=list[StaffRankRead])
async def list_ranks(
    category_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    school = await db.get(School, school_id)
    if school and school.ownership == SchoolOwnership.PUBLIC:
        condition = or_(StaffRank.school_id == school_id, StaffRank.school_id.is_(None))
    else:
        condition = StaffRank.school_id == school_id
    rows = await db.scalars(
        select(StaffRank).where(
            condition,
            StaffRank.category_id == category_id,
            StaffRank.is_active == True,
        ).order_by(StaffRank.title)
    )
    return [StaffRankRead.model_validate(r) for r in rows]


@router.post("/staff/ranks", response_model=StaffRankRead, status_code=201)
async def create_rank(
    req: StaffRankCreate,
    ids=Depends(require_permission("staff", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    cat = await db.get(StaffCategory, req.category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    rank = StaffRank(
        school_id=school_id,
        category_id=req.category_id,
        title=req.title.strip(),
        is_template=False,
        is_active=True,
    )
    db.add(rank)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Rank '{req.title}' already exists in this category.",
        )
    return StaffRankRead.model_validate(rank)
