"""
Academic year and term service.

Manages the hierarchy:  School → AcademicYear → AcademicTerm
Each school has at most one is_current AcademicYear and at most one
is_current AcademicTerm — enforced by a partial unique index on each table
(migration 161935b6a857), not just application logic, so a concurrent
request can't leave two rows simultaneously current.

set_current_term always cascades to make its own parent year current too,
atomically, in the same call — a term's is_current can never be True while
its year's is_current is False. set_current_year is the mirror: it unsets
any current term that doesn't belong to the newly-current year (but never
auto-picks a new one — a year can be current with no term chosen yet, a
normal transient state during setup). This pair is what prevents the
"current year has no current term, an unrelated year's term is current
instead" drift that a plain per-table "unset the others" implementation
allows with a single ordinary click on the wrong year's term.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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


def _validate_date_order(start_date, end_date, label: str) -> None:
    if end_date <= start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} end date must be after its start date.",
        )


# ── Academic Year ─────────────────────────────────────────────────────────────

async def create_year(
    req: AcademicYearCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicYear:
    _validate_date_order(req.start_date, req.end_date, "Academic year")
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
    # order_by + limit(1) is cheap defense-in-depth: the partial unique index
    # makes more than one current row per school impossible going forward,
    # but this keeps the query itself deterministic rather than depending on
    # that constraint alone (e.g. against any pre-migration data).
    return await db.scalar(
        select(AcademicYear)
        .where(AcademicYear.school_id == school_id, AcademicYear.is_current == True)
        .options(selectinload(AcademicYear.terms))
        .order_by(AcademicYear.start_date.desc())
        .limit(1)
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
    new_start = req.start_date if req.start_date is not None else year.start_date
    new_end = req.end_date if req.end_date is not None else year.end_date
    _validate_date_order(new_start, new_end, "Academic year")
    if req.name is not None:
        year.name = req.name.strip()
    year.start_date = new_start
    year.end_date = new_end
    await db.flush()
    return year


async def set_current_year(
    year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicYear:
    year = await get_year(year_id, school_id, db)
    # Setting a new current year unsets any currently-current term that
    # doesn't belong to it — a stale cross-year current term must never
    # survive its year losing "current" status. Deliberately does not
    # auto-pick a new current term for this year: a year can legitimately
    # be current with zero current term chosen yet (normal during setup).
    await db.execute(
        update(AcademicTerm)
        .where(
            AcademicTerm.school_id == school_id,
            AcademicTerm.is_current == True,
            AcademicTerm.academic_year_id != year_id,
        )
        .values(is_current=False)
    )
    await db.execute(
        update(AcademicYear)
        .where(AcademicYear.school_id == school_id, AcademicYear.is_current == True)
        .values(is_current=False)
    )
    year.is_current = True
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another current-year change happened at the same time — please retry.",
        )
    return year


# ── Academic Term ─────────────────────────────────────────────────────────────

async def _assert_term_dates_valid(
    year: AcademicYear,
    start_date,
    end_date,
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    exclude_term_id: uuid.UUID | None = None,
) -> None:
    """A term's dates must fall within its own year's range and must not
    overlap any sibling term already in that year — nonsense configurations
    with no legitimate exception, unlike e.g. the programme/stream mismatch
    override elsewhere in this codebase, so these are hard rejects."""
    _validate_date_order(start_date, end_date, "Term")
    if start_date < year.start_date or end_date > year.end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Term dates must fall within the academic year's range "
                   f"({year.start_date} – {year.end_date}).",
        )
    siblings_stmt = select(AcademicTerm).where(
        AcademicTerm.academic_year_id == year.id,
        AcademicTerm.school_id == school_id,
    )
    if exclude_term_id is not None:
        siblings_stmt = siblings_stmt.where(AcademicTerm.id != exclude_term_id)
    siblings = await db.scalars(siblings_stmt)
    for sib in siblings:
        if start_date <= sib.end_date and end_date >= sib.start_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Term dates overlap existing term '{sib.name}' "
                       f"({sib.start_date} – {sib.end_date}).",
            )


async def create_term(
    year_id: uuid.UUID,
    req: AcademicTermCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    year = await get_year(year_id, school_id, db)   # ownership check
    await _assert_term_dates_valid(year, req.start_date, req.end_date, school_id, db)
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
    user_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    term = await get_term(term_id, school_id, db)
    if req.start_date is not None or req.end_date is not None:
        new_start = req.start_date if req.start_date is not None else term.start_date
        new_end = req.end_date if req.end_date is not None else term.end_date
        year = await get_year(term.academic_year_id, school_id, db)
        await _assert_term_dates_valid(
            year, new_start, new_end, school_id, db, exclude_term_id=term.id,
        )
        term.start_date = new_start
        term.end_date = new_end
    if req.name is not None:
        term.name = req.name.strip()
    if req.block_owing_students is not None and req.block_owing_students != term.block_owing_students:
        term.block_owing_students = req.block_owing_students
        term.block_owing_students_set_by = user_id
        term.block_owing_students_set_at = datetime.now(timezone.utc)
    if req.results_locked is not None and req.results_locked != term.results_locked:
        term.results_locked = req.results_locked
        term.results_locked_by_id = user_id
        term.results_locked_at = datetime.now(timezone.utc)
    await db.flush()
    return term


async def set_current_term(
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AcademicTerm:
    """Setting a term current always cascades to make its own parent year
    current too, atomically — a term whose year isn't current can never be
    "the" current term. This is what makes it impossible to reproduce the
    documented drift (a stray term in a non-current year marked current
    while the real current year has none) via the normal set-current
    action, whichever term/year it's called on."""
    term = await get_term(term_id, school_id, db)
    year = await get_year(term.academic_year_id, school_id, db)
    # (a) unset whatever term was previously current anywhere in the school
    await db.execute(
        update(AcademicTerm)
        .where(AcademicTerm.school_id == school_id, AcademicTerm.is_current == True)
        .values(is_current=False)
    )
    # (b) unset whatever year was previously current, unless it's already
    # this term's own parent year
    await db.execute(
        update(AcademicYear)
        .where(
            AcademicYear.school_id == school_id,
            AcademicYear.is_current == True,
            AcademicYear.id != year.id,
        )
        .values(is_current=False)
    )
    # (c) + (d) set the target term and its parent year current, atomically
    term.is_current = True
    year.is_current = True
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another current year/term change happened at the same time — please retry.",
        )
    return term


async def get_current_term(school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm | None:
    return await db.scalar(
        select(AcademicTerm)
        .where(AcademicTerm.school_id == school_id, AcademicTerm.is_current == True)
        .order_by(AcademicTerm.start_date.desc())
        .limit(1)
    )


async def list_all_terms(school_id: uuid.UUID, db: AsyncSession) -> list[AcademicTerm]:
    rows = await db.scalars(
        select(AcademicTerm)
        .join(AcademicYear, AcademicYear.id == AcademicTerm.academic_year_id)
        .where(AcademicYear.school_id == school_id)
        .order_by(AcademicYear.start_date.desc(), AcademicTerm.term_number)
    )
    return list(rows)
