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
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SchoolLevel, SHSProgramme, Subject, SubjectCatalogue, SubjectType
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


async def update_programme(
    prog_id: uuid.UUID,
    req: ProgrammeUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> SHSProgramme:
    # Mirror list_programmes: match both school-owned and global (school_id=NULL) records.
    # list_programmes shows both, so a programme visible in the UI must be updatable too.
    prog = await db.scalar(
        select(SHSProgramme).where(
            SHSProgramme.id == prog_id,
            or_(SHSProgramme.school_id == school_id, SHSProgramme.school_id.is_(None)),
        )
    )
    if not prog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme not found.")

    # A shared (school_id=NULL) programme is used by every SHS school on the
    # platform — editing it must never mutate the shared row itself, or the
    # edit (rename, deactivate, ...) would silently apply to every other
    # school too. Fork a school-owned copy on first edit instead, and
    # re-point this school's own classes at the copy so their existing data
    # follows the edit; the original shared row is left untouched for
    # everyone else.
    if prog.school_id is None:
        copy = SHSProgramme(
            school_id=school_id, code=prog.code, name=prog.name, is_active=prog.is_active,
        )
        db.add(copy)
        await db.flush()
        await db.execute(
            update(Class)
            .where(Class.school_id == school_id, Class.programme_id == prog.id)
            .values(programme_id=copy.id)
        )
        prog = copy

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
