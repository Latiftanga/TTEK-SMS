"""
Academic router — years, terms, programmes, subjects, classes, teacher assignments.

GET endpoints: any authenticated school user.
POST/PATCH endpoints: require 'academic.manage' permission.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.models.academic import SchoolLevel
from app.schemas.academic import (
    AcademicTermCreate,
    AcademicTermUpdate,
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
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
    SubjectCreate,
    SubjectRead,
    SubjectTeacherAssign,
    SubjectTeacherRead,
    TermRead,
)
from app.services import academic_class as class_svc
from app.services import academic_subjects as subj_svc
from app.services import academic_year as year_svc

router = APIRouter(prefix="/academic", tags=["academic"])


@router.post("/years", response_model=AcademicYearRead, status_code=201)
async def create_year(
    req: AcademicYearCreate,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.create_year(req, school_id, db)
    return AcademicYearRead.model_validate(year)


@router.get("/years", response_model=list[AcademicYearRead])
async def list_years(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    years = await year_svc.list_years(school_id, db)
    return [AcademicYearRead.model_validate(y) for y in years]


@router.get("/years/current", response_model=AcademicYearRead | None)
async def get_current_year(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.get_current_year(school_id, db)
    return AcademicYearRead.model_validate(year) if year else None


@router.get("/years/{year_id}", response_model=AcademicYearRead)
async def get_year(
    year_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.get_year(year_id, school_id, db)
    return AcademicYearRead.model_validate(year)


@router.patch("/years/{year_id}", response_model=AcademicYearRead)
async def update_year(
    year_id: uuid.UUID,
    req: AcademicYearUpdate,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.update_year(year_id, req, school_id, db)
    return AcademicYearRead.model_validate(year)


@router.post("/years/{year_id}/set-current", response_model=AcademicYearRead)
async def set_current_year(
    year_id: uuid.UUID,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.set_current_year(year_id, school_id, db)
    return AcademicYearRead.model_validate(year)


@router.post("/years/{year_id}/terms", response_model=TermRead, status_code=201)
async def create_term(
    year_id: uuid.UUID,
    req: AcademicTermCreate,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    term = await year_svc.create_term(year_id, req, school_id, db)
    return TermRead.model_validate(term)


@router.get("/years/{year_id}/terms", response_model=list[TermRead])
async def list_terms(
    year_id: uuid.UUID,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    terms = await year_svc.list_terms(year_id, school_id, db)
    return [TermRead.model_validate(t) for t in terms]


@router.patch("/terms/{term_id}", response_model=TermRead)
async def update_term(
    term_id: uuid.UUID,
    req: AcademicTermUpdate,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    term = await year_svc.update_term(term_id, req, school_id, db)
    return TermRead.model_validate(term)


@router.post("/terms/{term_id}/set-current", response_model=TermRead)
async def set_current_term(
    term_id: uuid.UUID,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    term = await year_svc.set_current_term(term_id, school_id, db)
    return TermRead.model_validate(term)


@router.get("/terms/current", response_model=TermRead | None)
async def get_current_term(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    term = await year_svc.get_current_term(school_id, db)
    return TermRead.model_validate(term) if term else None


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
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    prog = await subj_svc.create_programme(req, school_id, db)
    return ProgrammeRead.model_validate(prog)


@router.get("/catalogue", response_model=list[CatalogueRead])
async def list_catalogue(
    level: SchoolLevel | None = Query(None),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    items = await subj_svc.list_catalogue(level, db)
    return [CatalogueRead.model_validate(i) for i in items]


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
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    subj = await subj_svc.create_subject(req, school_id, db)
    return SubjectRead.model_validate(subj)


@router.post("/classes", response_model=ClassRead, status_code=201)
async def create_class(
    req: ClassCreate,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.create_class(req, school_id, db)


@router.get("/classes", response_model=list[ClassRead])
async def list_classes(
    year_id: uuid.UUID = Query(..., description="Filter by academic year"),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.list_classes(year_id, school_id, db)


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
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.update_class(class_id, req, school_id, db)


@router.post("/classes/{class_id}/subjects", response_model=list[ClassSubjectRead], status_code=201)
async def assign_subjects(
    class_id: uuid.UUID,
    req: ClassSubjectAssign,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    added = await class_svc.assign_subjects(class_id, req, school_id, db)
    return [ClassSubjectRead.model_validate(cs) for cs in added]


@router.post("/classes/{class_id}/class-teacher", response_model=ClassTeacherRead, status_code=201)
async def assign_class_teacher(
    class_id: uuid.UUID,
    req: ClassTeacherAssign,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    ct = await class_svc.assign_class_teacher(class_id, req, school_id, db)
    return ClassTeacherRead.model_validate(ct)


@router.post("/classes/{class_id}/subject-teachers", response_model=SubjectTeacherRead, status_code=201)
async def assign_subject_teacher(
    class_id: uuid.UUID,
    req: SubjectTeacherAssign,
    ids=Depends(require_permission("academic", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    st = await class_svc.assign_subject_teacher(class_id, req, school_id, db)
    return SubjectTeacherRead.model_validate(st)
