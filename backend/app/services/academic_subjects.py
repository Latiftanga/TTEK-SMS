"""SHS programmes, subject catalogue, and school subjects.

SHS GUARD
---------
Programmes and elective subjects only make sense for SHS schools:
  - list_programmes  returns [] for non-SHS (graceful, no 422)
  - create_programme raises 422 for non-SHS
  - create_subject   raises 422 when the linked catalogue entry is ELECTIVE
    and the school is not SHS; core/custom subjects are unrestricted

PROGRAMME CATALOGUE
--------------------
Which programmes a school runs depends on its own resources — one SHS school
may offer only Business, another may run all of them. Nothing is offered
automatically: the standard GES programmes (school_id=NULL) are a read-only
catalogue, exactly like SubjectCatalogue is for subjects, except there's no
separate table for it — the shared rows serve as the catalogue directly.
list_programmes returns only a school's own adopted/custom rows;
list_programme_catalogue returns the shared rows not yet adopted (matched by
code, since SHSProgramme has no catalogue_id FK the way Subject does);
adopt_programme copies one in as a new school-owned row. The shared rows
themselves are never editable (update_programme only matches a school's own
rows) — adopt first, then edit your own copy.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import SchoolLevel, SHSProgramme, Subject, SubjectCatalogue, SubjectType
from app.models.school import School, SchoolType
from app.schemas.academic import ProgrammeCreate, ProgrammeUpdate, SubjectCreate, SubjectUpdate


async def _require_shs(school_id: uuid.UUID, db: AsyncSession) -> None:
    school = await db.get(School, school_id)
    if not school or school.school_type != SchoolType.SHS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Programmes and elective subjects are only available to SHS schools.",
        )


async def list_programmes(school_id: uuid.UUID, db: AsyncSession) -> list[SHSProgramme]:
    """This school's own adopted/custom programmes only — not the shared
    catalogue (see list_programme_catalogue). Includes inactive ones so the
    admin UI's status filter can find and reactivate a deactivated one."""
    school = await db.get(School, school_id)
    if not school or school.school_type != SchoolType.SHS:
        return []
    rows = await db.scalars(
        select(SHSProgramme)
        .where(SHSProgramme.school_id == school_id)
        .order_by(SHSProgramme.name)
    )
    return list(rows)


async def list_programme_catalogue(school_id: uuid.UUID, db: AsyncSession) -> list[SHSProgramme]:
    """The shared GES standard programmes this school hasn't adopted yet."""
    school = await db.get(School, school_id)
    if not school or school.school_type != SchoolType.SHS:
        return []
    adopted_codes = set((await db.scalars(
        select(SHSProgramme.code).where(SHSProgramme.school_id == school_id)
    )).all())
    rows = await db.scalars(
        select(SHSProgramme)
        .where(SHSProgramme.school_id.is_(None), SHSProgramme.is_active == True)
        .order_by(SHSProgramme.name)
    )
    return [p for p in rows if p.code not in adopted_codes]


async def adopt_programme(
    catalogue_programme_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> SHSProgramme:
    """Copy a shared catalogue programme in as this school's own row."""
    await _require_shs(school_id, db)
    source = await db.scalar(
        select(SHSProgramme).where(
            SHSProgramme.id == catalogue_programme_id, SHSProgramme.school_id.is_(None),
        )
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue programme not found.")
    existing = await db.scalar(
        select(SHSProgramme).where(SHSProgramme.school_id == school_id, SHSProgramme.code == source.code)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{source.name}' is already offered by this school.",
        )
    prog = SHSProgramme(school_id=school_id, code=source.code, name=source.name, is_active=True)
    db.add(prog)
    await db.flush()
    return prog


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


async def update_programme(
    prog_id: uuid.UUID,
    req: ProgrammeUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> SHSProgramme:
    """Only a school's own adopted/custom programme is editable — the shared
    catalogue is read-only (browse via list_programme_catalogue, copy in via
    adopt_programme, then edit your own copy)."""
    prog = await db.scalar(
        select(SHSProgramme).where(SHSProgramme.id == prog_id, SHSProgramme.school_id == school_id)
    )
    if not prog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme not found.")
    if req.code is not None:
        prog.code = req.code.upper().strip()
    if req.name is not None:
        prog.name = req.name.strip()
    if req.is_active is not None:
        prog.is_active = req.is_active
    await db.flush()
    return prog


async def update_subject(
    subject_id: uuid.UUID,
    req: SubjectUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> Subject:
    subj = await db.scalar(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )
    if not subj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")
    if req.code is not None:
        subj.code = req.code.upper().strip()
    if req.name is not None:
        subj.name = req.name.strip()
    if req.is_active is not None:
        subj.is_active = req.is_active
    await db.flush()
    return subj


async def list_catalogue(level: SchoolLevel | None, db: AsyncSession) -> list[SubjectCatalogue]:
    q = select(SubjectCatalogue).where(SubjectCatalogue.is_active == True)
    if level:
        q = q.where(SubjectCatalogue.level == level)
    rows = await db.scalars(q.order_by(SubjectCatalogue.name))
    return list(rows)


async def list_subjects(school_id: uuid.UUID, db: AsyncSession) -> list[Subject]:
    """Includes inactive subjects so the admin UI's status filter can find
    and reactivate a deactivated one — a hardcoded active-only filter here
    would make Deactivate a one-way trip with no way back through the UI."""
    rows = await db.scalars(
        select(Subject)
        .where(Subject.school_id == school_id)
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
        if not cat:
            raise HTTPException(404, "Catalogue subject not found.")
        if cat.subject_type == SubjectType.ELECTIVE:
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
