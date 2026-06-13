"""
GradingScale and Grade CRUD, plus grade resolution at query time.

INVARIANT: Grade is NEVER stored on Score — it is resolved here from the
school's active GradingScale every time a score is approved.

When a GradingScale's bands change, clear_cached_grades() must be called so
cached_grade_label is recalculated on next approval.
"""
from __future__ import annotations
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import Grade, GradingScale, Score
from app.schemas.assessments import GradeCreate, GradingScaleCreate, GradingScaleRead


async def create_grading_scale(
    req: GradingScaleCreate, school_id: uuid.UUID, db: AsyncSession
) -> GradingScale:
    if req.is_default:
        await db.execute(
            update(GradingScale)
            .where(GradingScale.school_id == school_id, GradingScale.is_default.is_(True))
            .values(is_default=False)
        )
    scale = GradingScale(
        school_id=school_id,
        name=req.name,
        description=req.description,
        is_default=req.is_default,
    )
    db.add(scale)
    await db.flush()
    await db.refresh(scale, ["grades"])
    return scale


async def list_grading_scales(school_id: uuid.UUID, db: AsyncSession) -> list[GradingScale]:
    rows = await db.scalars(
        select(GradingScale)
        .where(GradingScale.school_id == school_id, GradingScale.is_active.is_(True))
        .order_by(GradingScale.is_default.desc(), GradingScale.name)
    )
    scales = list(rows)
    for s in scales:
        await db.refresh(s, ["grades"])
    return scales


async def get_grading_scale(
    scale_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> GradingScale:
    scale = await db.scalar(
        select(GradingScale).where(
            GradingScale.id == scale_id, GradingScale.school_id == school_id
        )
    )
    if not scale:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grading scale not found.")
    await db.refresh(scale, ["grades"])
    return scale


async def add_grade(
    scale_id: uuid.UUID, req: GradeCreate, school_id: uuid.UUID, db: AsyncSession
) -> Grade:
    scale = await get_grading_scale(scale_id, school_id, db)
    grade = Grade(
        grading_scale_id=scale.id,
        min_score=req.min_score,
        max_score=req.max_score,
        letter_grade=req.letter_grade,
        label=req.label,
        gpa_points=req.gpa_points,
        remarks=req.remarks,
    )
    db.add(grade)
    await db.flush()
    await clear_cached_grades(scale_id, school_id, db)
    return grade


async def delete_grade(
    scale_id: uuid.UUID, grade_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    scale = await get_grading_scale(scale_id, school_id, db)
    grade = await db.scalar(
        select(Grade).where(Grade.id == grade_id, Grade.grading_scale_id == scale.id)
    )
    if not grade:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade band not found.")
    await db.delete(grade)
    await clear_cached_grades(scale_id, school_id, db)


async def resolve_grade(
    raw_score: Decimal, school_id: uuid.UUID, db: AsyncSession
) -> str | None:
    """Return letter_grade from the school's default grading scale, or None."""
    scale = await db.scalar(
        select(GradingScale).where(
            GradingScale.school_id == school_id,
            GradingScale.is_default.is_(True),
            GradingScale.is_active.is_(True),
        )
    )
    if not scale:
        return None
    await db.refresh(scale, ["grades"])
    for band in scale.grades:
        if band.min_score <= raw_score <= band.max_score:
            return band.letter_grade
    return None


async def clear_cached_grades(
    scale_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    """Nullify cached_grade_label on all approved scores for this school."""
    await db.execute(
        update(Score)
        .where(Score.school_id == school_id, Score.is_approved.is_(True))
        .values(cached_grade_label=None)
    )
