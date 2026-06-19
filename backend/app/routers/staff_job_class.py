"""Job class management endpoints.

GET  /staff/job-classes        — list all job classes visible to this school
POST /staff/job-classes        — create a school-specific custom job class

GES template classes (school_id=NULL, is_template=True) are seeded globally
and visible to all schools but cannot be created or modified via the API.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.staff import StaffJobClass
from app.schemas.staff import StaffJobClassCreate, StaffJobClassRead

router = APIRouter(prefix="/staff/job-classes", tags=["staff"])


@router.get("", response_model=list[StaffJobClassRead])
async def list_job_classes(
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Return all job classes available to this school (GES templates + custom)."""
    _, school_id = ids
    rows = await db.scalars(
        select(StaffJobClass).where(
            or_(StaffJobClass.school_id == school_id, StaffJobClass.school_id.is_(None)),
            StaffJobClass.is_active == True,
        ).order_by(StaffJobClass.name)
    )
    return [StaffJobClassRead.model_validate(jc) for jc in rows]


@router.post("", response_model=StaffJobClassRead, status_code=201)
async def create_job_class(
    req: StaffJobClassCreate,
    ids=Depends(require_permission("staff", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Create a school-specific custom job class."""
    _, school_id = ids
    jc = StaffJobClass(
        school_id=school_id,
        name=req.name.strip(),
        code=req.code.strip().upper(),
        is_template=False,
        is_active=True,
    )
    db.add(jc)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"A job class with code '{req.code.upper()}' already exists for this school.",
        )
    return StaffJobClassRead.model_validate(jc)
