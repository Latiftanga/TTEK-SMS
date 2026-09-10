"""
CurriculumUnit list/update — the admin QA view and manual-correction path
for the AI-extracted structured curriculum data (services/
curriculum_unit_extraction.py), plus the read path the lesson-plan "pick a
unit" flow uses (services/lesson_plans.py::_resolve_curriculum_unit).
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum_materials import CurriculumMaterial
from app.models.curriculum_units import CurriculumUnit
from app.schemas.curriculum_units import CurriculumUnitRead, CurriculumUnitUpdate


def _to_read(u: CurriculumUnit) -> CurriculumUnitRead:
    return CurriculumUnitRead.model_validate(u)


async def _assert_material_owned(material_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    exists = await db.scalar(
        select(CurriculumMaterial.id).where(CurriculumMaterial.id == material_id, CurriculumMaterial.school_id == school_id)
    )
    if not exists:
        raise HTTPException(404, "Curriculum material not found.")


async def list_units(material_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> list[CurriculumUnitRead]:
    await _assert_material_owned(material_id, school_id, db)
    rows = await db.scalars(
        select(CurriculumUnit)
        .where(CurriculumUnit.material_id == material_id, CurriculumUnit.school_id == school_id)
        .order_by(CurriculumUnit.sequence_number)
    )
    return [_to_read(r) for r in rows]


async def update_unit(
    unit_id: uuid.UUID, req: CurriculumUnitUpdate, school_id: uuid.UUID, db: AsyncSession,
) -> CurriculumUnitRead:
    unit = await db.scalar(
        select(CurriculumUnit).where(CurriculumUnit.id == unit_id, CurriculumUnit.school_id == school_id)
    )
    if not unit:
        raise HTTPException(404, "Curriculum unit not found.")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    await db.flush()
    return _to_read(unit)
