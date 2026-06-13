"""SHS programmes, subject catalogue, and school subjects.

SHS GUARD
---------
Programmes and elective subjects only make sense for SHS schools:
  - list_programmes  returns [] for non-SHS (graceful, no 422)
  - create_programme raises 422 for non-SHS
  - create_subject   raises 422 when the linked catalogue entry is ELECTIVE
    and the school is not SHS; core/custom subjects are unrestricted
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import SchoolLevel, SHSProgramme, Subject, SubjectCatalogue, SubjectType
from app.models.school import School, SchoolType
from app.schemas.academic import ProgrammeCreate, SubjectCreate


async def _require_shs(school_id: uuid.UUID, db: AsyncSession) -> None:
    school = await db.get(School, school_id)
    if not school or school.school_type != SchoolType.SHS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Programmes and elective subjects are only available to SHS schools.",
        )


async def list_programmes(school_id: uuid.UUID, db: AsyncSession) -> list[SHSProgramme]:
    school = await db.get(School, school_id)
    if not school or school.school_type != SchoolType.SHS:
        return []
    rows = await db.scalars(
        select(SHSProgramme)
        .where(
            or_(SHSProgramme.school_id == school_id, SHSProgramme.school_id.is_(None)),
            SHSProgramme.is_active == True,
        )
        .order_by(SHSProgramme.name)
    )
    return list(rows)


async def create_programme(
    req: ProgrammeCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> SHSProgramme:
    await _require_shs(school_id, db)
    prog = SHSProgramme(
        school_id=school_id,
        code=req.code.upper().strip(),
        name=req.name.strip(),
        is_active=True,
    )
    db.add(prog)
    await db.flush()
    return prog


async def list_catalogue(level: SchoolLevel | None, db: AsyncSession) -> list[SubjectCatalogue]:
    q = select(SubjectCatalogue).where(SubjectCatalogue.is_active == True)
    if level:
        q = q.where(SubjectCatalogue.level == level)
    rows = await db.scalars(q.order_by(SubjectCatalogue.name))
    return list(rows)


async def list_subjects(school_id: uuid.UUID, db: AsyncSession) -> list[Subject]:
    rows = await db.scalars(
        select(Subject)
        .where(Subject.school_id == school_id, Subject.is_active == True)
        .order_by(Subject.name)
    )
    return list(rows)


async def create_subject(
    req: SubjectCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> Subject:
    if req.catalogue_id:
        cat = await db.get(SubjectCatalogue, req.catalogue_id)
        if cat and cat.subject_type == SubjectType.ELECTIVE:
            await _require_shs(school_id, db)
    subj = Subject(
        school_id=school_id,
        catalogue_id=req.catalogue_id,
        code=req.code.upper().strip(),
        name=req.name.strip(),
        is_active=True,
    )
    db.add(subj)
    await db.flush()
    return subj
