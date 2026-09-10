"""
Lesson plan CRUD — a personal weekly planner for subject teachers.

Scoped by core/teacher_scope.py::resolve_assessment_scope(), reused as-is —
identical ownership boundary to Assessments (the caller's own SubjectTeacher
(class, subject) pairs this year, unrestricted for assessments.approve_scores
holders). Deliberately no current-term restriction (unlike scoring/
attendance/behaviour) — planning ahead for a future term, or adding
reflection notes to a past one, are both legitimate personal-planner uses;
only the chosen week must actually fall within the chosen term's own dates.
"""
from __future__ import annotations
import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import resolve_assessment_scope, year_for_term
from app.models.academic import AcademicTerm, ClassSubject
from app.models.curriculum_materials import CurriculumMaterial
from app.models.curriculum_units import CurriculumUnit
from app.models.lesson_plans import CurriculumStandard, LessonPlan
from app.schemas.curriculum_units import CurriculumUnitRead
from app.schemas.lesson_plans import LessonPlanCreate, LessonPlanRead, LessonPlanUpdate
from app.services.subject_roster import class_subject_exists


def _normalize_week_start(d: date) -> date:
    """Any date in the target week -> that week's Monday, so the frontend
    and backend never disagree about which week a date belongs to."""
    return d - timedelta(days=d.weekday())


def _to_read(lp: LessonPlan) -> LessonPlanRead:
    return LessonPlanRead.model_validate(lp)


async def _check_scope(
    class_id: uuid.UUID, subject_id: uuid.UUID, academic_term_id: uuid.UUID | None, user_id: uuid.UUID, db: AsyncSession,
) -> None:
    year_id = await year_for_term(academic_term_id, db)
    if year_id is None:
        return
    scope = await resolve_assessment_scope(user_id, year_id, db)
    if scope is not None and (class_id, subject_id) not in scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")


async def _get_term(academic_term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm:
    term = await db.scalar(
        select(AcademicTerm).where(AcademicTerm.id == academic_term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")
    return term


async def _resolve_curriculum_standard(
    curriculum_standard_id: uuid.UUID | None, school_id: uuid.UUID, db: AsyncSession,
) -> CurriculumStandard | None:
    if curriculum_standard_id is None:
        return None
    cs = await db.scalar(
        select(CurriculumStandard).where(
            CurriculumStandard.id == curriculum_standard_id,
            (CurriculumStandard.school_id == school_id) | (CurriculumStandard.school_id.is_(None)),
        )
    )
    if not cs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Curriculum standard not found.")
    return cs


async def _resolve_curriculum_unit(
    curriculum_unit_id: uuid.UUID | None, class_id: uuid.UUID, subject_id: uuid.UUID,
    school_id: uuid.UUID, db: AsyncSession,
) -> CurriculumUnit | None:
    """A second, independent optional autofill source — a specific
    machine-extracted unit the teacher picked from a short list (never
    auto-mapped from the calendar date, see models/curriculum_units.py).
    Ownership check: the unit's parent CurriculumMaterial must be uploaded
    against the exact (class, subject) being planned, not just any material
    at this school."""
    if curriculum_unit_id is None:
        return None
    unit = await db.scalar(
        select(CurriculumUnit)
        .join(CurriculumMaterial, CurriculumMaterial.id == CurriculumUnit.material_id)
        .join(ClassSubject, ClassSubject.id == CurriculumMaterial.class_subject_id)
        .where(
            CurriculumUnit.id == curriculum_unit_id,
            CurriculumUnit.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
        )
    )
    if not unit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Curriculum unit not found.")
    return unit


def _reference_autofill_from(
    cu: CurriculumUnit | None, cs: CurriculumStandard | None,
) -> tuple[str | None, str | None, str | None]:
    """content_standard/indicator/learning_objectives autofill precedence —
    picked CurriculumUnit (the richer, document-cited source) over matched
    CurriculumStandard — shared by create_lesson_plan and update_lesson_plan
    so the precedence formula itself lives in exactly one place. Each caller
    layers its own guard on top (create: only when the request didn't supply
    the field itself; update: only when the field is still blank and wasn't
    part of this request) rather than this helper, since those guards
    genuinely differ between the two."""
    content_standard = (cu.content_standard if cu else None) or (f"{cs.strand} — {cs.sub_strand}" if cs else None)
    indicator = (cu.indicator if cu else None) or (cs.indicator_code if cs else None)
    learning_objectives = (cu.learning_objectives if cu else None) or (cs.objective_text if cs else None)
    return content_standard, indicator, learning_objectives


async def list_curriculum_units_for_planning(
    class_id: uuid.UUID, subject_id: uuid.UUID, academic_term_id: uuid.UUID,
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> list[CurriculumUnitRead]:
    """Powers the "pick a unit" flow on the lesson-plans page — gated on
    lesson_plans.view + the caller's own SubjectTeacher scope (same as every
    other read in this file), not documents.view, since an ordinary
    TEACHER-position subject teacher (the exact audience for this feature)
    doesn't hold that broader admin permission."""
    await _check_scope(class_id, subject_id, academic_term_id, user_id, db)
    rows = await db.scalars(
        select(CurriculumUnit)
        .join(CurriculumMaterial, CurriculumMaterial.id == CurriculumUnit.material_id)
        .join(ClassSubject, ClassSubject.id == CurriculumMaterial.class_subject_id)
        .where(
            ClassSubject.class_id == class_id, ClassSubject.subject_id == subject_id,
            CurriculumUnit.school_id == school_id,
        )
        .order_by(CurriculumMaterial.created_at.desc(), CurriculumUnit.sequence_number)
    )
    return [CurriculumUnitRead.model_validate(r) for r in rows]


async def create_lesson_plan(
    req: LessonPlanCreate, school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    term = await _get_term(req.academic_term_id, school_id, db)
    if not await class_subject_exists(req.class_id, req.subject_id, school_id, db):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class/subject not found.")
    await _check_scope(req.class_id, req.subject_id, req.academic_term_id, user_id, db)

    week_start = _normalize_week_start(req.week_start_date)
    if not (term.start_date <= week_start <= term.end_date):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"That week falls outside {term.name}'s dates ({term.start_date} to {term.end_date}).",
        )

    cs = await _resolve_curriculum_standard(req.curriculum_standard_id, school_id, db)
    cu = await _resolve_curriculum_unit(req.curriculum_unit_id, req.class_id, req.subject_id, school_id, db)
    # Precedence: explicit request field > picked CurriculumUnit > matched
    # CurriculumStandard — the unit is the richer, document-cited source
    # when a teacher has one to pick from.
    auto_content_standard, auto_indicator, auto_learning_objectives = _reference_autofill_from(cu, cs)
    content_standard = req.content_standard or auto_content_standard
    indicator = req.indicator or auto_indicator
    learning_objectives = req.learning_objectives or auto_learning_objectives

    lp = LessonPlan(
        school_id=school_id,
        class_id=req.class_id,
        subject_id=req.subject_id,
        academic_term_id=req.academic_term_id,
        week_start_date=week_start,
        topic=req.topic.strip(),
        content_standard=content_standard,
        indicator=indicator,
        learning_objectives=learning_objectives,
        strand=cu.strand if cu else None,
        sub_strand=cu.sub_strand if cu else None,
        core_competencies=req.core_competencies,
        teaching_resources=req.teaching_resources,
        activities=req.activities,
        assessment_strategy=req.assessment_strategy,
        reflection_notes=req.reflection_notes,
        created_by_id=staff_id,
        curriculum_standard_id=cs.id if cs else None,
        curriculum_unit_id=cu.id if cu else None,
    )
    db.add(lp)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A lesson plan already exists for this class, subject, and week.",
        )
    return _to_read(lp)


async def list_lesson_plans(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    *,
    week_start_date: date | None = None,
) -> list[LessonPlanRead]:
    # academic_term_id is required (not optional) specifically so the scope
    # check below always has something to resolve a year from — matches
    # /assessments' own GET convention (class_id + term_id both required),
    # avoiding a would-be gap where a missing term silently no-ops scoping.
    await _check_scope(class_id, subject_id, academic_term_id, user_id, db)

    where = [
        LessonPlan.class_id == class_id,
        LessonPlan.subject_id == subject_id,
        LessonPlan.school_id == school_id,
        LessonPlan.academic_term_id == academic_term_id,
    ]
    if week_start_date is not None:
        where.append(LessonPlan.week_start_date == _normalize_week_start(week_start_date))

    rows = (await db.scalars(
        select(LessonPlan).where(*where).order_by(LessonPlan.week_start_date.desc())
    )).all()
    return [_to_read(r) for r in rows]


async def get_lesson_plan(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> LessonPlan:
    lp = await db.scalar(
        select(LessonPlan).where(LessonPlan.id == lesson_plan_id, LessonPlan.school_id == school_id)
    )
    if not lp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson plan not found.")
    await _check_scope(lp.class_id, lp.subject_id, lp.academic_term_id, user_id, db)
    return lp


async def update_lesson_plan(
    lesson_plan_id: uuid.UUID, req: LessonPlanUpdate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    fields = req.model_dump(exclude_unset=True)
    cs = None
    cu = None
    if "curriculum_standard_id" in fields and fields["curriculum_standard_id"] is not None:
        cs = await _resolve_curriculum_standard(fields["curriculum_standard_id"], school_id, db)
    if "curriculum_unit_id" in fields and fields["curriculum_unit_id"] is not None:
        cu = await _resolve_curriculum_unit(fields["curriculum_unit_id"], lp.class_id, lp.subject_id, school_id, db)
    for field, value in fields.items():
        setattr(lp, field, value.strip() if field == "topic" and value else value)
    if cs or cu:
        # Same autofill precedence as create_lesson_plan (see
        # _reference_autofill_from) — only fills a field that's still blank
        # after applying this request's own explicit values, never
        # overwrites one the teacher set (here or in an earlier request).
        auto_content_standard, auto_indicator, auto_learning_objectives = _reference_autofill_from(cu, cs)
        if not lp.content_standard and "content_standard" not in fields:
            lp.content_standard = auto_content_standard
        if not lp.indicator and "indicator" not in fields:
            lp.indicator = auto_indicator
        if not lp.learning_objectives and "learning_objectives" not in fields:
            lp.learning_objectives = auto_learning_objectives
        if cu:
            if not lp.strand:
                lp.strand = cu.strand
            if not lp.sub_strand:
                lp.sub_strand = cu.sub_strand
    await db.flush()
    return _to_read(lp)


async def delete_lesson_plan(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> None:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    await db.delete(lp)
