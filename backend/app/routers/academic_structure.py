"""
Academic structure router — programmes, subjects, classes, teacher assignments.
Years and terms: see academic.py.

GET endpoints: any authenticated school user.
POST/PATCH: require 'academic.create' or 'academic.edit'.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.models.academic import SchoolLevel
from app.schemas.academic import (
    CatalogueRead,
    ClassCreate,
    ClassRead,
    ClassSubjectAssign,
    ClassSubjectRead,
    ClassTeacherAssign,
    ClassTeacherRead,
    ClassUpdate,
    ProgrammeCreate,
    ProgrammeRead,
    ProgrammeUpdate,
    SubjectCreate,
    SubjectRead,
    SubjectTeacherAssign,
    SubjectTeacherRead,
    SubjectUpdate,
)
from app.services import academic_class as class_svc
from app.services import academic_subjects as subj_svc
from app.services import academic_teachers as teacher_svc

router = APIRouter(prefix="/academic", tags=["academic"])


# ── Programmes ────────────────────────────────────────────────────────────────

@router.get("/programmes", response_model=list[ProgrammeRead])
async def list_programmes(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    progs = await subj_svc.list_programmes(school_id, db)
    return [ProgrammeRead.model_validate(p) for p in progs]


@router.post("/programmes", response_model=ProgrammeRead, status_code=201)
async def create_programme(
    req: ProgrammeCreate,
    ids=Depends(require_permission("academic", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    prog = await subj_svc.create_programme(req, school_id, db)
    return ProgrammeRead.model_validate(prog)


@router.patch("/programmes/{programme_id}", response_model=ProgrammeRead)
async def update_programme(
    programme_id: uuid.UUID,
    req: ProgrammeUpdate,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    prog = await subj_svc.update_programme(programme_id, req, school_id, db)
    return ProgrammeRead.model_validate(prog)


# ── Subject catalogue ─────────────────────────────────────────────────────────

@router.get("/catalogue", response_model=list[CatalogueRead])
async def list_catalogue(
    level: SchoolLevel | None = Query(None),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    items = await subj_svc.list_catalogue(level, db)
    return [CatalogueRead.model_validate(i) for i in items]


# ── Subjects ──────────────────────────────────────────────────────────────────

@router.get("/subjects", response_model=list[SubjectRead])
async def list_subjects(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    subjects = await subj_svc.list_subjects(school_id, db)
    return [SubjectRead.model_validate(s) for s in subjects]


@router.post("/subjects", response_model=SubjectRead, status_code=201)
async def create_subject(
    req: SubjectCreate,
    ids=Depends(require_permission("academic", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    subj = await subj_svc.create_subject(req, school_id, db)
    return SubjectRead.model_validate(subj)


@router.patch("/subjects/{subject_id}", response_model=SubjectRead)
async def update_subject(
    subject_id: uuid.UUID,
    req: SubjectUpdate,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    subj = await subj_svc.update_subject(subject_id, req, school_id, db)
    return SubjectRead.model_validate(subj)


# ── Classes ───────────────────────────────────────────────────────────────────

@router.post("/classes", response_model=ClassRead, status_code=201)
async def create_class(
    req: ClassCreate,
    ids=Depends(require_permission("academic", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.create_class(req, school_id, db)


@router.get("/classes", response_model=list[ClassRead])
async def list_classes(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.list_classes(school_id, db)


@router.get("/classes/{class_id}", response_model=ClassRead)
async def get_class(
    class_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.get_class(class_id, school_id, db)


@router.patch("/classes/{class_id}", response_model=ClassRead)
async def update_class(
    class_id: uuid.UUID,
    req: ClassUpdate,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.update_class(class_id, req, school_id, db)


# ── Class subjects & teachers ─────────────────────────────────────────────────

@router.get("/classes/{class_id}/subjects", response_model=list[ClassSubjectRead])
async def list_class_subjects(
    class_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    rows = await class_svc.list_class_subjects(class_id, school_id, db)
    return [ClassSubjectRead.model_validate(cs) for cs in rows]


@router.post("/classes/{class_id}/subjects", response_model=list[ClassSubjectRead], status_code=201)
async def assign_subjects(
    class_id: uuid.UUID,
    req: ClassSubjectAssign,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    added = await class_svc.assign_subjects(class_id, req, school_id, db)
    return [ClassSubjectRead.model_validate(cs) for cs in added]


@router.get("/classes/{class_id}/class-teacher", response_model=ClassTeacherRead | None)
async def get_class_teacher(
    class_id: uuid.UUID,
    year_id: uuid.UUID = Query(...),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    ct = await teacher_svc.get_class_teacher(class_id, year_id, school_id, db)
    return ClassTeacherRead.model_validate(ct) if ct else None


@router.post("/classes/{class_id}/class-teacher", response_model=ClassTeacherRead, status_code=201)
async def assign_class_teacher(
    class_id: uuid.UUID,
    req: ClassTeacherAssign,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    ct = await teacher_svc.assign_class_teacher(class_id, req, school_id, db)
    return ClassTeacherRead.model_validate(ct)


@router.get("/classes/{class_id}/subject-teachers", response_model=list[SubjectTeacherRead])
async def list_subject_teachers(
    class_id: uuid.UUID,
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    rows = await teacher_svc.list_subject_teachers(class_id, term_id, school_id, db)
    return [SubjectTeacherRead.model_validate(st) for st in rows]


@router.post("/classes/{class_id}/subject-teachers", response_model=SubjectTeacherRead, status_code=201)
async def assign_subject_teacher(
    class_id: uuid.UUID,
    req: SubjectTeacherAssign,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    st = await teacher_svc.assign_subject_teacher(class_id, req, school_id, db)
    return SubjectTeacherRead.model_validate(st)


@router.delete("/classes/{class_id}/subjects/{subject_id}", status_code=204)
async def remove_class_subject(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await class_svc.remove_class_subject(class_id, subject_id, school_id, db)
