"""AssessmentType CRUD — split out of services/assessment.py to stay under the 300-line cap."""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import Assessment, AssessmentType
from app.schemas.assessment_type import (
    AssessmentTypeCreate, AssessmentTypeRead, AssessmentTypeUpdate, _check_strategy_matches_multiplicity,
)


def _type_read(t: AssessmentType) -> AssessmentTypeRead:
    return AssessmentTypeRead.model_validate(t)


async def create_assessment_type(
    req: AssessmentTypeCreate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentTypeRead:
    existing = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.school_id == school_id,
            (AssessmentType.code == req.code) | (AssessmentType.name == req.name),
        )
    )
    if existing:
        field = "code" if existing.code == req.code else "name"
        value = req.code if field == "code" else req.name
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Assessment type with {field} '{value}' already exists.",
        )
    t = AssessmentType(
        school_id=school_id,
        name=req.name,
        code=req.code,
        weight=req.weight,
        category=req.category,
        allow_multiple_entries=req.allow_multiple_entries,
        aggregation_strategy=req.aggregation_strategy,
    )
    db.add(t)
    await db.flush()
    return _type_read(t)


async def update_assessment_type(
    type_id: uuid.UUID, req: AssessmentTypeUpdate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentTypeRead:
    t = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.id == type_id, AssessmentType.school_id == school_id
        )
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment type not found.")
    if req.name is not None or req.code is not None:
        conflict = await db.scalar(
            select(AssessmentType).where(
                AssessmentType.school_id == school_id,
                AssessmentType.id != type_id,
                (AssessmentType.name == req.name) | (AssessmentType.code == req.code),
            )
        )
        if conflict:
            field = "name" if conflict.name == req.name else "code"
            value = req.name if field == "name" else req.code
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Assessment type with {field} '{value}' already exists.",
            )
    # create_assessment() guards against a *new* second Assessment ever being
    # recorded once allow_multiple_entries is False, but nothing previously
    # stopped narrowing an existing multi-entry type down to single-entry
    # after real data already violated that — resolve_type_score() would
    # then raise at report-card time for every class/term that already has
    # more than one recorded entry. Check before mutating anything, so a
    # rejected update never leaves the row dirty in the session.
    new_allow_multiple = req.allow_multiple_entries if req.allow_multiple_entries is not None else t.allow_multiple_entries
    if not new_allow_multiple:
        violation = await db.execute(
            select(Assessment.class_id)
            .where(Assessment.assessment_type_id == type_id)
            .group_by(Assessment.class_id, Assessment.subject_id, Assessment.academic_term_id)
            .having(func.count() > 1)
            .limit(1)
        )
        if violation.first() is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{t.name} already has more than one assessment recorded for the same "
                "class, subject, and term — resolve those before making it single-entry.",
            )

    if req.name is not None:
        t.name = req.name
    if req.code is not None:
        t.code = req.code
    if req.weight is not None:
        t.weight = req.weight
    if req.category is not None:
        t.category = req.category
    if req.allow_multiple_entries is not None:
        t.allow_multiple_entries = req.allow_multiple_entries
    if req.aggregation_strategy is not None:
        t.aggregation_strategy = req.aggregation_strategy
    if req.is_active is not None:
        t.is_active = req.is_active
    # The schema only cross-checks allow_multiple_entries/aggregation_strategy
    # when both arrive in the same request — a partial update touching just
    # one is checked here against the resulting full row instead, so a type
    # can never end up in an invalid NONE/allow_multiple combination either way.
    try:
        _check_strategy_matches_multiplicity(t.allow_multiple_entries, t.aggregation_strategy)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    await db.flush()
    return _type_read(t)


async def list_assessment_types(
    school_id: uuid.UUID, db: AsyncSession
) -> list[AssessmentTypeRead]:
    # Includes inactive types so the admin UI's status filter can find and
    # reactivate a deactivated one — a hardcoded active-only filter here
    # would make Deactivate a one-way trip with no way back through the UI
    # (same fix already applied to list_subjects()). The frontend picker
    # used at assessment-creation time filters to active-only client-side.
    rows = await db.scalars(
        select(AssessmentType)
        .where(AssessmentType.school_id == school_id)
        .order_by(AssessmentType.name)
    )
    return [_type_read(t) for t in rows]


async def delete_assessment_type(
    type_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    t = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.id == type_id, AssessmentType.school_id == school_id
        )
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment type not found.")
    # Assessment.assessment_type_id has no ondelete clause (Postgres defaults
    # to RESTRICT), so a hard delete against an in-use type would otherwise
    # surface as a raw IntegrityError. Check first and give a clean 409
    # pointing at deactivation, the safe alternative for a type with real data.
    count = await db.scalar(
        select(func.count()).select_from(Assessment).where(Assessment.assessment_type_id == type_id)
    )
    if count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{t.name} has {count} assessment(s) recorded against it and can't be deleted "
            "— deactivate it instead to hide it from new assessments.",
        )
    await db.delete(t)
    await db.flush()
