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
from app.models.academic import AcademicTerm, Class, SHSProgramme, Subject
from app.models.lesson_plans import LessonPlan
from app.schemas.lesson_plans import LessonPlanCreate, LessonPlanRead, LessonPlanUpdate
from app.services import ai_config
from app.services.student_display import _class_display_name
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

    lp = LessonPlan(
        school_id=school_id,
        class_id=req.class_id,
        subject_id=req.subject_id,
        academic_term_id=req.academic_term_id,
        week_start_date=week_start,
        topic=req.topic.strip(),
        content_standard=req.content_standard,
        indicator=req.indicator,
        learning_objectives=req.learning_objectives,
        core_competencies=req.core_competencies,
        teaching_resources=req.teaching_resources,
        activities=req.activities,
        assessment_strategy=req.assessment_strategy,
        reflection_notes=req.reflection_notes,
        created_by_id=staff_id,
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
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(lp, field, value.strip() if field == "topic" and value else value)
    await db.flush()
    return _to_read(lp)


async def delete_lesson_plan(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> None:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    await db.delete(lp)


_AI_SYSTEM_PROMPT = (
    "You are an assistant helping a Ghanaian teacher draft a weekly lesson "
    "plan aligned with the GES Standards-Based Curriculum. Write plain text "
    "(no markdown headers or tables), organized under these labeled "
    "sections: Learning Objectives, Core Competencies, Teaching Resources, "
    "Activities, and Assessment Strategy. Keep it concise and practical — "
    "this is a starting draft for the teacher to edit, not a finished plan."
)


async def draft_with_ai(
    class_id: uuid.UUID, subject_id: uuid.UUID, topic: str,
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> str:
    """Returns a single free-text draft — AiDriver.generate() returns plain
    str with no structured-output contract, so this is shown to the teacher
    as a suggestion to review/copy from, never auto-saved into the form's
    individual fields."""
    await ai_config.check_daily_limit(school_id, user_id, db)  # raises 429 if exhausted
    driver = await ai_config.get_active_driver(school_id, db)  # raises 503 if unconfigured

    subject = await db.get(Subject, subject_id)
    cls = await db.get(Class, class_id)
    prog_name = None
    if cls and cls.programme_id:
        prog = await db.get(SHSProgramme, cls.programme_id)
        prog_name = prog.name if prog else None
    class_label = _class_display_name(cls.level, cls.year_group, prog_name, cls.stream) if cls else "the class"
    subject_name = subject.name if subject else "the subject"

    prompt = f"Draft a weekly lesson plan for {class_label}, subject: {subject_name}. Topic: {topic}."
    draft_text = await driver.generate(prompt, _AI_SYSTEM_PROMPT)

    await ai_config.increment_usage(school_id, user_id)
    return draft_text
