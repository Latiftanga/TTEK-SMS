"""
Academic router — years and terms only.
Programmes, subjects, classes: see academic_structure.py.

GET endpoints: any authenticated school user.
POST/PATCH: require 'academic.create' or 'academic.edit'.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.schemas.academic import (
    AcademicTermCreate,
    AcademicTermUpdate,
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
    TermRead,
)
from app.services import academic_year as year_svc

router = APIRouter(prefix="/academic", tags=["academic"])


@router.post("/years", response_model=AcademicYearRead, status_code=201)
async def create_year(
    req: AcademicYearCreate,
    ids=Depends(require_permission("academic", "create")),
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
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.update_year(year_id, req, school_id, db)
    return AcademicYearRead.model_validate(year)


@router.post("/years/{year_id}/set-current", response_model=AcademicYearRead)
async def set_current_year(
    year_id: uuid.UUID,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    year = await year_svc.set_current_year(year_id, school_id, db)
    return AcademicYearRead.model_validate(year)


@router.post("/years/{year_id}/terms", response_model=TermRead, status_code=201)
async def create_term(
    year_id: uuid.UUID,
    req: AcademicTermCreate,
    ids=Depends(require_permission("academic", "create")),
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
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    term = await year_svc.update_term(term_id, req, school_id, user_id, db)
    return TermRead.model_validate(term)


@router.post("/terms/{term_id}/set-current", response_model=TermRead)
async def set_current_term(
    term_id: uuid.UUID,
    ids=Depends(require_permission("academic", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    term = await year_svc.set_current_term(term_id, school_id, db)
    return TermRead.model_validate(term)


@router.get("/terms", response_model=list[TermRead])
async def list_all_terms(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    terms = await year_svc.list_all_terms(school_id, db)
    return [TermRead.model_validate(t) for t in terms]


@router.get("/terms/current", response_model=TermRead | None)
async def get_current_term(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    term = await year_svc.get_current_term(school_id, db)
    return TermRead.model_validate(term) if term else None
