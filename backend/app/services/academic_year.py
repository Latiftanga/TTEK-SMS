"""
Academic year and term service.

Manages the hierarchy:  School → AcademicYear → AcademicTerm
Each school has multiple years; at most one should be is_current at a time.
Each year has up to 3 terms; at most one should be is_current at a time.

set_current_year / set_current_term unset all other is_current flags in the
same transaction so the "only one current" invariant is never broken mid-flight.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicTerm, AcademicYear
from app.schemas.academic import (
    AcademicTermCreate,
    AcademicTermUpdate,
    AcademicYearCreate,
    AcademicYearUpdate,
)


# ── Academic Year ─────────────────────────────────────────────────────────────

async def create_year(
    req: AcademicYearCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicYear:
    year = AcademicYear(
        school_id=school_id,
        name=req.name.strip(),
        start_date=req.start_date,
        end_date=req.end_date,
        is_current=False,
    )
    db.add(year)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An academic year named '{req.name}' already exists for this school.",
        )
    # Eagerly load the terms collection so Pydantic serialization doesn't trigger
    # a lazy SELECT outside an async context (MissingGreenlet error).
    await db.refresh(year, attribute_names=["terms"])
    return year


async def get_current_year(school_id: uuid.UUID, db: AsyncSession) -> AcademicYear | None:
    return await db.scalar(
        select(AcademicYear)
        .where(AcademicYear.school_id == school_id, AcademicYear.is_current == True)
        .options(selectinload(AcademicYear.terms))
    )


async def list_years(school_id: uuid.UUID, db: AsyncSession) -> list[AcademicYear]:
    rows = await db.scalars(
        select(AcademicYear)
        .where(AcademicYear.school_id == school_id)
        .options(selectinload(AcademicYear.terms))
        .order_by(AcademicYear.start_date.desc())
    )
    return list(rows)


async def get_year(
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicYear:
    year = await db.scalar(
        select(AcademicYear)
        .where(AcademicYear.id == year_id, AcademicYear.school_id == school_id)
        .options(selectinload(AcademicYear.terms))
    )
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found.")
    return year


async def update_year(
    year_id: uuid.UUID,
    req: AcademicYearUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicYear:
    year = await get_year(year_id, school_id, db)
    if req.name is not None:
        year.name = req.name.strip()
    if req.start_date is not None:
        year.start_date = req.start_date
    if req.end_date is not None:
        year.end_date = req.end_date
    await db.flush()
    return year


async def set_current_year(
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicYear:
    year = await get_year(year_id, school_id, db)
    await db.execute(
        update(AcademicYear)
        .where(AcademicYear.school_id == school_id, AcademicYear.is_current == True)
        .values(is_current=False)
    )
    year.is_current = True
    await db.flush()
    return year


# ── Academic Term ─────────────────────────────────────────────────────────────

async def create_term(
    year_id: uuid.UUID,
    req: AcademicTermCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    await get_year(year_id, school_id, db)   # ownership check
    term = AcademicTerm(
        school_id=school_id,
        academic_year_id=year_id,
        term_number=req.term_number,
        name=req.name.strip(),
        start_date=req.start_date,
        end_date=req.end_date,
        is_current=False,
    )
    db.add(term)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Term {req.term_number} already exists for this academic year.",
        )
    return term


async def list_terms(
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[AcademicTerm]:
    await get_year(year_id, school_id, db)   # ownership check
    rows = await db.scalars(
        select(AcademicTerm)
        .where(
            AcademicTerm.academic_year_id == year_id,
            AcademicTerm.school_id == school_id,
        )
        .order_by(AcademicTerm.term_number)
    )
    return list(rows)


async def get_term(
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    term = await db.scalar(
        select(AcademicTerm)
        .where(AcademicTerm.id == term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found.")
    return term


async def update_term(
    term_id: uuid.UUID,
    req: AcademicTermUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    term = await get_term(term_id, school_id, db)
    if req.name is not None:
        term.name = req.name.strip()
    if req.start_date is not None:
        term.start_date = req.start_date
    if req.end_date is not None:
        term.end_date = req.end_date
    await db.flush()
    return term


async def set_current_term(
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    term = await get_term(term_id, school_id, db)
    await db.execute(
        update(AcademicTerm)
        .where(AcademicTerm.school_id == school_id, AcademicTerm.is_current == True)
        .values(is_current=False)
    )
    term.is_current = True
    await db.flush()
    return term


async def get_current_term(school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm | None:
    return await db.scalar(
        select(AcademicTerm)
        .where(AcademicTerm.school_id == school_id, AcademicTerm.is_current == True)
    )
