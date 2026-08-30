"""
AI-assisted lesson plan generation — the staged skeleton -> expand workflow.

Two real backend calls, not one button: generate_skeleton() produces the
cheap-to-iterate essential-questions/strategies/resources/differentiation
outline; generate_lessons() (requires an existing skeleton) resolves this
week's real scheduled occurrences (services/lesson_plan_occurrences.py) and
expands into one lesson body per occurrence plus an assessment block.
regenerate_lesson()/regenerate_assessment() replace just one slice of an
already-generated plan without touching the rest. Shared prompt-building/
logging/validation helpers live in services/lesson_plan_prompt.py, split out
to stay under the 300-line cap.

Every AI call is logged (LessonPlanGenerationLog) with the prompt and model
version for audit, mirroring ScoreAuditLog/AssessmentAuditLog's shape.
generated_content is additive on LessonPlan — every existing scalar field
(topic, activities, assessment_strategy, reflection_notes, ...) is left
completely untouched by everything in this file.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import year_for_term
from app.models.lesson_plans import LessonPlan, LessonPlanGenerationStage, LessonPlanStatus
from app.schemas.lesson_plans import (
    AssessmentBlock, CurriculumReferenceSuggestion, GeneratedLessonsResponse,
    LessonBody, LessonEntry, LessonPlanRead, LessonPlanReviewRequest, LessonPlanSkeleton,
)
from app.services import ai_config
from app.services.ai_driver import generate_json
from app.services.lesson_plan_occurrences import resolve_week_occurrences
from app.services.lesson_plan_prompt import (
    apply_curriculum_reference, build_context, get_curriculum_excerpts,
    get_ready_driver, get_content, log_generation, validate_lessons, SYSTEM_GUARDRAILS,
)
from app.services.lesson_plans import _to_read, get_lesson_plan


async def generate_skeleton(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    driver, cfg = await get_ready_driver(school_id, user_id, db)

    context = await build_context(lp, school_id, db)
    # Grounds the AI's proposed content standard/indicator in the school's
    # own uploaded curriculum material when there is one — a teacher never
    # has to type these fields themselves, see
    # lesson_plan_prompt.py::propose_curriculum_reference()'s own docstring
    # for why this path bundles the idea into one call instead of a
    # second one (unlike the chat path, which has no other structured
    # call to piggyback on).
    needs_reference = not (lp.content_standard and lp.indicator and lp.learning_objectives)
    reference_ask = ""
    if needs_reference:
        excerpts = await get_curriculum_excerpts(lp.class_id, lp.subject_id, lp.topic, school_id, db)
        reference_ask = (
            "\n\nAlso propose the content standard, learning indicator (a GES-style "
            "code, e.g. B7.1.1.1), and learning objectives for this topic — use the "
            "curriculum excerpts below if they state one explicitly, never invent a "
            "code that wasn't given to you; otherwise give your best general "
            f"estimate.\n\nCurriculum excerpts:\n{excerpts}"
        )
    prompt = (
        f"{context}\n\nProduce 2-4 essential questions, 3-5 pedagogical "
        "strategies, 3-6 teaching & learning resources, and one paragraph "
        "of differentiation notes (how to support struggling and stretch "
        f"advanced learners) for this lesson.{reference_ask}"
    )
    skeleton = await generate_json(driver, prompt, SYSTEM_GUARDRAILS, LessonPlanSkeleton)
    await log_generation(
        school_id, lp.id, LessonPlanGenerationStage.SKELETON, prompt,
        cfg.provider.value, cfg.model or "default", staff_id, db,
    )
    await ai_config.increment_usage(school_id, user_id, cfg)

    content = get_content(lp)
    content.essential_questions = skeleton.essential_questions
    content.pedagogical_strategies = skeleton.pedagogical_strategies
    content.teaching_learning_resources = skeleton.teaching_learning_resources
    content.differentiation_notes = skeleton.differentiation_notes
    lp.generated_content = content.model_dump(mode="json")
    if needs_reference:
        apply_curriculum_reference(lp, CurriculumReferenceSuggestion(
            content_standard=skeleton.content_standard,
            indicator=skeleton.indicator,
            learning_objectives=skeleton.learning_objectives,
        ))
    await db.flush()
    return _to_read(lp)


async def generate_lessons(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    content = get_content(lp)
    if not content.essential_questions:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Generate a skeleton first.")

    year_id = await year_for_term(lp.academic_term_id, db)
    if year_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Academic term has no year.")
    week_end = lp.week_start_date + timedelta(days=6)
    occurrences = await resolve_week_occurrences(
        lp.class_id, lp.subject_id, year_id, lp.week_start_date, week_end, school_id, db,
    )
    if not occurrences:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No real scheduled occurrences found for this class/subject this week "
            "(check the timetable and calendar for that week).",
        )

    driver, cfg = await get_ready_driver(school_id, user_id, db)

    context = await build_context(lp, school_id, db)
    occ_lines = "\n".join(
        f"- {o.lesson_date.isoformat()}, {o.start_time}-{o.end_time}" for o in occurrences
    )
    prompt = (
        f"{context}\n\nEssential questions: {content.essential_questions}\n"
        f"Pedagogical strategies: {content.pedagogical_strategies}\n\n"
        f"There are exactly {len(occurrences)} scheduled lessons this week:\n{occ_lines}\n\n"
        f"Produce exactly {len(occurrences)} lesson entries in the same order as listed above "
        "(introduction, main lesson, closure for each), sized to fit each lesson's own "
        "duration. Also produce one assessment block: a formative check (mode, task, mark "
        "scheme) and a transcript/summative assessment (mode, task, rubric)."
    )
    result = await generate_json(driver, prompt, SYSTEM_GUARDRAILS, GeneratedLessonsResponse)
    await log_generation(
        school_id, lp.id, LessonPlanGenerationStage.LESSONS, prompt,
        cfg.provider.value, cfg.model or "default", staff_id, db,
    )
    await ai_config.increment_usage(school_id, user_id, cfg)

    if len(result.lessons) != len(occurrences):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"The AI produced {len(result.lessons)} lessons but {len(occurrences)} were expected.",
        )

    lessons: list[LessonEntry] = []
    for occ, body in zip(occurrences, result.lessons):
        duration = (
            (occ.end_time.hour * 60 + occ.end_time.minute)
            - (occ.start_time.hour * 60 + occ.start_time.minute)
        )
        lessons.append(LessonEntry(
            school_calendar_id=occ.school_calendar_id, period_id=occ.period_id,
            lesson_date=occ.lesson_date, start_time=occ.start_time, end_time=occ.end_time,
            duration_minutes=duration, introduction=body.introduction,
            main_lesson=body.main_lesson, closure=body.closure, delivery_status="DRAFT",
        ))

    content.lessons = lessons
    content.assessment = result.assessment
    content.occurrence_mismatch = False
    content.generation_warnings = validate_lessons(lessons, lp.indicator or lp.content_standard)
    lp.generated_content = content.model_dump(mode="json")
    await db.flush()
    return _to_read(lp)


async def regenerate_lesson(
    lesson_plan_id: uuid.UUID, school_calendar_id: uuid.UUID, period_id: uuid.UUID,
    school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    content = get_content(lp)
    idx = next(
        (i for i, l in enumerate(content.lessons)
         if l.school_calendar_id == school_calendar_id and l.period_id == period_id),
        None,
    )
    if idx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That lesson occurrence is not part of this plan.")

    driver, cfg = await get_ready_driver(school_id, user_id, db)

    existing = content.lessons[idx]
    context = await build_context(lp, school_id, db)
    prompt = (
        f"{context}\n\nThis specific lesson is on {existing.lesson_date.isoformat()}, "
        f"{existing.start_time}-{existing.end_time} ({existing.duration_minutes} minutes). "
        "Produce a fresh introduction, main lesson, and closure for just this one lesson."
    )
    body = await generate_json(driver, prompt, SYSTEM_GUARDRAILS, LessonBody)
    await log_generation(
        school_id, lp.id, LessonPlanGenerationStage.REGENERATE_LESSON, prompt,
        cfg.provider.value, cfg.model or "default", staff_id, db,
    )
    await ai_config.increment_usage(school_id, user_id, cfg)

    content.lessons[idx] = existing.model_copy(update={
        "introduction": body.introduction, "main_lesson": body.main_lesson,
        "closure": body.closure, "delivery_status": "DRAFT",
    })
    lp.generated_content = content.model_dump(mode="json")
    await db.flush()
    return _to_read(lp)


async def regenerate_assessment(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    content = get_content(lp)
    if not content.lessons:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Generate lessons first.")

    driver, cfg = await get_ready_driver(school_id, user_id, db)

    context = await build_context(lp, school_id, db)
    prompt = (
        f"{context}\n\nProduce one assessment block for this week's lessons: a formative "
        "check (mode, task, mark scheme) and a transcript/summative assessment (mode, task, rubric)."
    )
    assessment = await generate_json(driver, prompt, SYSTEM_GUARDRAILS, AssessmentBlock)
    await log_generation(
        school_id, lp.id, LessonPlanGenerationStage.REGENERATE_ASSESSMENT, prompt,
        cfg.provider.value, cfg.model or "default", staff_id, db,
    )
    await ai_config.increment_usage(school_id, user_id, cfg)

    content.assessment = assessment
    lp.generated_content = content.model_dump(mode="json")
    await db.flush()
    return _to_read(lp)


async def review_lesson_plan(
    lesson_plan_id: uuid.UUID, req: LessonPlanReviewRequest,
    school_id: uuid.UUID, reviewer_staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    """No _check_scope call, deliberately: the router already gated this on
    the narrow lesson_plans.approve permission, which is itself the
    authorization to act on ANY plan school-wide — re-applying the
    plan-owner's own SubjectTeacher scope on top would defeat the point of
    granting review rights to someone who isn't also that class's subject
    teacher."""
    lp = await db.scalar(select(LessonPlan).where(LessonPlan.id == lesson_plan_id, LessonPlan.school_id == school_id))
    if not lp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson plan not found.")

    if req.status == LessonPlanStatus.APPROVED and lp.generated_content:
        content = get_content(lp)
        if content.lessons:
            year_id = await year_for_term(lp.academic_term_id, db)
            fresh = await resolve_week_occurrences(
                lp.class_id, lp.subject_id, year_id, lp.week_start_date,
                lp.week_start_date + timedelta(days=6), school_id, db,
            ) if year_id else []
            fresh_ids = {(o.school_calendar_id, o.period_id) for o in fresh}
            stored_ids = {(l.school_calendar_id, l.period_id) for l in content.lessons}
            if fresh_ids != stored_ids:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "The scheduled occurrences for this plan have changed since it was "
                    "generated (timetable or calendar changed) — regenerate lessons before approving.",
                )

    lp.status = req.status
    lp.reviewed_by_staff_id = reviewer_staff_id
    lp.review_notes = req.review_notes
    lp.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return _to_read(lp)
