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
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import Grade, GradingScale, Score
from app.schemas.grading import GradeCreate, GradingScaleCreate, GradingScaleRead, GradingScaleUpdate


async def create_grading_scale(
    req: GradingScaleCreate, school_id: uuid.UUID, db: AsyncSession
) -> GradingScale:
    existing = await db.scalar(
        select(GradingScale).where(
            GradingScale.school_id == school_id,
            GradingScale.name == req.name,
        )
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Grading scale with name '{req.name}' already exists.",
        )
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
    """A school's own scales (active or not — so a deactivated one can still
    be found and reactivated through the UI, same fix already applied to
    list_subjects()/list_assessment_types()), then the shared system
    default(s) — active only, since no per-school endpoint can ever manage
    that row anyway. See resolve_grade() for the matching fallback used when
    scoring."""
    rows = await db.scalars(
        select(GradingScale)
        .where(
            or_(
                GradingScale.school_id == school_id,
                and_(GradingScale.school_id.is_(None), GradingScale.is_active.is_(True)),
            )
        )
        .options(selectinload(GradingScale.grades))
        .order_by(GradingScale.school_id.is_(None), GradingScale.is_default.desc(), GradingScale.name)
    )
    return list(rows)


async def get_grading_scale(
    scale_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> GradingScale:
    scale = await db.scalar(
        select(GradingScale)
        .where(GradingScale.id == scale_id, GradingScale.school_id == school_id)
        .options(selectinload(GradingScale.grades))
    )
    if not scale:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grading scale not found.")
    return scale


async def update_grading_scale(
    scale_id: uuid.UUID, req: GradingScaleUpdate, school_id: uuid.UUID, db: AsyncSession
) -> GradingScale:
    scale = await get_grading_scale(scale_id, school_id, db)
    if req.name is not None and req.name != scale.name:
        conflict = await db.scalar(
            select(GradingScale).where(
                GradingScale.school_id == school_id,
                GradingScale.name == req.name,
                GradingScale.id != scale_id,
            )
        )
        if conflict:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Grading scale with name '{req.name}' already exists.",
            )

    # Snapshot which scale actually governs resolution before mutating —
    # compared against the same snapshot taken after, below, so both
    # "explicitly switch default" AND "deactivate the scale that happened to
    # be the effective default" (silently falling back to the next one in
    # get_default_scale_with_bands' priority order) are caught by one check,
    # instead of two separate ad hoc flags.
    effective_before = await get_default_scale_with_bands(school_id, db)

    if req.is_default is True and not scale.is_default:
        await db.execute(
            update(GradingScale)
            .where(GradingScale.school_id == school_id, GradingScale.is_default.is_(True))
            .values(is_default=False)
        )
    if req.name is not None:
        scale.name = req.name
    if req.description is not None:
        scale.description = req.description
    if req.is_default is not None:
        scale.is_default = req.is_default
    if req.is_active is not None:
        scale.is_active = req.is_active
    await db.flush()

    effective_after = await get_default_scale_with_bands(school_id, db)
    effective_before_id = effective_before.id if effective_before else None
    effective_after_id = effective_after.id if effective_after else None
    if effective_before_id != effective_after_id:
        # Every previously-approved score was graded against whichever scale
        # effectively governed resolution at the time — a change here is
        # exactly as grade-affecting as editing a band (add_grade/
        # delete_grade already clear on that), or report cards silently keep
        # showing letter grades resolved from the OLD effective scale forever.
        await _wipe_cached_grades(school_id, db)

    await db.refresh(scale, ["grades"])
    return scale


async def delete_grading_scale(
    scale_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    """Hard-deletes a school-owned scale (never the shared platform default —
    get_grading_scale's school_id filter already makes that unreachable).
    Blocked while it's the active default: deleting it out from under
    resolve_grade() would just silently fall back to the next scale in
    get_default_scale_with_bands' priority order with no chance to clear
    cached grades first, unlike every other grade-affecting change here —
    set a different scale as default (or deactivate it, which does clear
    cleanly) before deleting."""
    scale = await get_grading_scale(scale_id, school_id, db)
    if scale.is_default:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{scale.name} is the active default and can't be deleted — "
            "set a different scale as default first.",
        )
    await db.delete(scale)
    await db.flush()


async def add_grade(
    scale_id: uuid.UUID, req: GradeCreate, school_id: uuid.UUID, db: AsyncSession
) -> Grade:
    scale = await get_grading_scale(scale_id, school_id, db)
    overlap = await db.scalar(
        select(Grade).where(
            Grade.grading_scale_id == scale.id,
            Grade.min_score <= req.max_score,
            Grade.max_score >= req.min_score,
        )
    )
    if overlap:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Range {req.min_score}–{req.max_score} overlaps with existing band "
            f"{overlap.min_score}–{overlap.max_score} ({overlap.letter_grade}).",
        )
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


async def get_default_scale_with_bands(
    school_id: uuid.UUID, db: AsyncSession
) -> GradingScale | None:
    """The school's own default GradingScale, falling back to the shared
    system default (school_id IS NULL, seeded by scripts/seed_reference_data.py)
    if the school hasn't created one — a school's own default, once created,
    always takes priority. Bands eager-loaded, highest score first (the
    relationship's own order_by="Grade.min_score.desc()").

    Shared by resolve_grade() (letter-grade lookup at approval time) and the
    report card / transcript grade-legend section (services/report_card.py,
    services/transcript.py) — one fallback rule, not two copies of it.
    """
    scale = await db.scalar(
        select(GradingScale)
        .where(
            GradingScale.school_id == school_id,
            GradingScale.is_default.is_(True),
            GradingScale.is_active.is_(True),
        )
        .options(selectinload(GradingScale.grades))
    )
    if not scale:
        scale = await db.scalar(
            select(GradingScale)
            .where(
                GradingScale.school_id.is_(None),
                GradingScale.is_default.is_(True),
                GradingScale.is_active.is_(True),
            )
            .options(selectinload(GradingScale.grades))
        )
    return scale


def grade_legend_rows(scale: GradingScale | None) -> list[dict]:
    """Flatten a GradingScale's bands into plain dicts for the report card /
    transcript "Grade Interpretation" legend — shared by both templates so
    they can't drift into showing different band data for the same school."""
    if not scale:
        return []
    return [
        {
            "letter_grade": band.letter_grade,
            "gpa_points": band.gpa_points,
            "min_score": band.min_score,
            "max_score": band.max_score,
            "label": band.label,
        }
        for band in scale.grades
    ]


def resolve_grade_from_scale(percentage: Decimal, scale: GradingScale | None) -> str | None:
    """Band-match a percentage against an already-loaded scale — the pure,
    no-query half of resolve_grade(), split out so a caller that needs to
    resolve grades for several percentages against the *same* scale (e.g.
    report_card.py resolving one grade per subject total) doesn't re-fetch
    the scale once per call."""
    if not scale:
        return None
    for band in scale.grades:
        if band.min_score <= percentage <= band.max_score:
            return band.letter_grade
    return None


async def resolve_grade(
    percentage: Decimal, school_id: uuid.UUID, db: AsyncSession
) -> str | None:
    """Return letter_grade from the school's default grading scale, or None.

    `percentage` must already be normalized to 0-100 — Grade bands are defined
    as percentage ranges (e.g. GES A1 = 80-100), not raw marks. Callers scoring
    against a non-100 max_score (see services/scoring.py::approve_scores) must
    convert before calling this.
    """
    scale = await get_default_scale_with_bands(school_id, db)
    return resolve_grade_from_scale(percentage, scale)


async def clear_cached_grades(
    scale_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    """Nullify cached_grade_label on all approved scores for this school —
    but only when `scale_id` is actually the scale currently governing
    resolution (get_default_scale_with_bands' own priority: the school's own
    default, else the shared platform default). resolve_grade() only ever
    reads from that one scale, never a non-default one — add_grade/
    delete_grade previously wiped every score's grade label school-wide
    whenever *any* scale was edited, including a brand new, unused draft
    scale that had never resolved a single score. A school with more than
    one GradingScale (a normal, supported setup — is_default exists
    specifically to pick one among several) would see every report card
    silently lose its letter grades the moment someone tinkered with an
    unrelated scale."""
    effective = await get_default_scale_with_bands(school_id, db)
    if effective is None or effective.id != scale_id:
        return
    await _wipe_cached_grades(school_id, db)


async def _wipe_cached_grades(school_id: uuid.UUID, db: AsyncSession) -> None:
    """The actual, unconditional nullify — callers (clear_cached_grades,
    update_grading_scale's effective-scale-changed check) decide when it's
    warranted."""
    await db.execute(
        update(Score)
        .where(Score.school_id == school_id, Score.is_approved.is_(True))
        .values(cached_grade_label=None)
    )
