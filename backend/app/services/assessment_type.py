"""AssessmentType CRUD — split out of services/assessment.py to stay under the 300-line cap."""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import AssessmentType
from app.schemas.assessments import AssessmentTypeCreate, AssessmentTypeRead, AssessmentTypeUpdate


def _type_read(t: AssessmentType) -> AssessmentTypeRead:
    return AssessmentTypeRead.model_validate(t)


async def create_assessment_type(
    req: AssessmentTypeCreate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentTypeRead:
    existing = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.school_id == school_id,
            (AssessmentType.code == req.code) | (AssessmentType.name == req.name),
        )
    )
    if existing:
        field = "code" if existing.code == req.code else "name"
        value = req.code if field == "code" else req.name
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Assessment type with {field} '{value}' already exists.",
        )
    t = AssessmentType(
        school_id=school_id,
        name=req.name,
        code=req.code,
        weight=req.weight,
    )
    db.add(t)
    await db.flush()
    return _type_read(t)


async def update_assessment_type(
    type_id: uuid.UUID, req: AssessmentTypeUpdate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentTypeRead:
    t = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.id == type_id, AssessmentType.school_id == school_id
        )
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment type not found.")
    if req.name is not None or req.code is not None:
        conflict = await db.scalar(
            select(AssessmentType).where(
                AssessmentType.school_id == school_id,
                AssessmentType.id != type_id,
                (AssessmentType.name == req.name) | (AssessmentType.code == req.code),
            )
        )
        if conflict:
            field = "name" if conflict.name == req.name else "code"
            value = req.name if field == "name" else req.code
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Assessment type with {field} '{value}' already exists.",
            )
    if req.name is not None:
        t.name = req.name
    if req.code is not None:
        t.code = req.code
    if req.weight is not None:
        t.weight = req.weight
    await db.flush()
    return _type_read(t)


async def list_assessment_types(
    school_id: uuid.UUID, db: AsyncSession
) -> list[AssessmentTypeRead]:
    rows = await db.scalars(
        select(AssessmentType)
        .where(AssessmentType.school_id == school_id, AssessmentType.is_active.is_(True))
        .order_by(AssessmentType.name)
    )
    return [_type_read(t) for t in rows]
