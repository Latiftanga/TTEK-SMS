"""
Curriculum standard CRUD — minimal, admin-facing (gated on the existing
academic.* permissions, same tier as Subject/SHSProgramme structural setup,
no new permission introduced for this). Starts empty; a school's own rows
(school_id set) coexist with any future shared GES-wide seed (school_id
NULL) exactly like SubjectCatalogue. See models/lesson_plans.py for the
full design note.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson_plans import CurriculumStandard
from app.schemas.lesson_plans import CurriculumStandardCreate, CurriculumStandardRead


def _to_read(cs: CurriculumStandard) -> CurriculumStandardRead:
    return CurriculumStandardRead.model_validate(cs)


async def create_curriculum_standard(
    req: CurriculumStandardCreate, school_id: uuid.UUID, db: AsyncSession,
) -> CurriculumStandardRead:
    cs = CurriculumStandard(school_id=school_id, **req.model_dump())
    db.add(cs)
    await db.flush()
    return _to_read(cs)


async def list_curriculum_standards(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    subject_catalogue_id: uuid.UUID | None = None,
    level: str | None = None,
    year_group: int | None = None,
    q: str | None = None,
    include_inactive: bool = False,
) -> list[CurriculumStandardRead]:
    where = [or_(CurriculumStandard.school_id == school_id, CurriculumStandard.school_id.is_(None))]
    if not include_inactive:
        where.append(CurriculumStandard.is_active.is_(True))
    if subject_catalogue_id is not None:
        where.append(CurriculumStandard.subject_catalogue_id == subject_catalogue_id)
    if level is not None:
        where.append(CurriculumStandard.level == level)
    if year_group is not None:
        where.append(CurriculumStandard.year_group == year_group)
    if q:
        like = f"%{q}%"
        where.append(or_(
            CurriculumStandard.strand.ilike(like),
            CurriculumStandard.sub_strand.ilike(like),
            CurriculumStandard.indicator_code.ilike(like),
            CurriculumStandard.objective_text.ilike(like),
        ))
    rows = await db.scalars(
        select(CurriculumStandard).where(*where)
        .order_by(CurriculumStandard.school_id.is_(None).desc(), CurriculumStandard.indicator_code)
    )
    return [_to_read(r) for r in rows]


async def set_curriculum_standard_active(
    curriculum_standard_id: uuid.UUID, is_active: bool, school_id: uuid.UUID, db: AsyncSession,
) -> CurriculumStandardRead:
    # Only a school's own rows can be retired here — the shared GES-wide
    # catalogue (school_id NULL) is read-only through this endpoint, same
    # "shared template, no self-service edit" convention as SubjectCatalogue.
    cs = await db.scalar(
        select(CurriculumStandard).where(CurriculumStandard.id == curriculum_standard_id, CurriculumStandard.school_id == school_id)
    )
    if not cs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Curriculum standard not found.")
    cs.is_active = is_active
    await db.flush()
    return _to_read(cs)
