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
generated_content is additive on LessonPlan — reflection_notes and topic
are untouched by everything in this file (topic is set once at creation,
reflection_notes is filled in only after teaching). teaching_resources/
activities/assessment_strategy ARE derived from generated_content once it
exists (see lesson_plan_prompt.py::sync_legacy_fields_from_content) — only
the first time each becomes available, never overwritten again — so the
"Plan details" panel reads as a complete plan instead of permanently blank
fields for a teacher who only ever used chat/generation.
"""
from __future__ import annotations
import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import year_for_term
from app.models.lesson_plans import LessonPlanGenerationStage
from app.schemas.lesson_plans import (
    AssessmentBlock, CurriculumReferenceSuggestion, GeneratedLessonsResponse,
    LessonBody, LessonEntry, LessonPlanRead, LessonPlanSkeleton,
)
from app.services import ai_config
from app.services.ai_driver import generate_json
from app.services.lesson_plan_occurrences import get_occurrences_or_require_count
from app.services.lesson_plan_prompt import (
    apply_curriculum_reference, build_context, sync_legacy_fields_from_content,
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
    # call to piggyback on). The excerpts themselves are already embedded
    # in `context` above (build_context grounds every stage the same way),
    # so this ask just references them rather than re-fetching/re-embedding.
    needs_reference = not (lp.content_standard and lp.indicator and lp.learning_objectives)
    reference_ask = ""
    if needs_reference:
        reference_ask = (
            "\n\nAlso propose the content standard, learning indicator (a GES-style "
            "code, e.g. B7.1.1.1), and learning objectives for this topic — use the "
            "curriculum excerpts above if they state one explicitly, never invent a "
            "code that wasn't given to you; otherwise give your best general estimate."
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
    sync_legacy_fields_from_content(lp, content)
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
    *, lesson_count: int | None = None,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    content = get_content(lp)
    if not content.essential_questions:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Generate a skeleton first.")

    year_id = await year_for_term(lp.academic_term_id, db)
    if year_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Academic term has no year.")
    week_end = lp.week_start_date + timedelta(days=6)
    # Real timetable data stays authoritative whenever it exists —
    # lesson_count is only ever consulted when this class+subject genuinely
    # has none for this week (see get_occurrences_or_require_count's own
    # docstring); occurrences is None specifically in that fallback case.
    occurrences = await get_occurrences_or_require_count(
        lp.class_id, lp.subject_id, year_id, lp.week_start_date, week_end, school_id, db, lesson_count,
    )

    driver, cfg = await get_ready_driver(school_id, user_id, db)

    context = await build_context(lp, school_id, db)
    if occurrences is not None:
        n = len(occurrences)
        occ_lines = "\n".join(f"- {o.lesson_date.isoformat()}, {o.start_time}-{o.end_time}" for o in occurrences)
    else:
        n = lesson_count
        occ_lines = (
            f"No confirmed timetable exists for this class/subject this week — plan "
            f"{n} generic lessons for the week, evenly weighted, no specific dates/times."
        )
    prompt = (
        f"{context}\n\nEssential questions: {content.essential_questions}\n"
        f"Pedagogical strategies: {content.pedagogical_strategies}\n\n"
        f"There are exactly {n} scheduled lessons this week:\n{occ_lines}\n\n"
        f"Produce exactly {n} lesson entries in the same order as listed above "
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

    if len(result.lessons) != n:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"The AI produced {len(result.lessons)} lessons but {n} were expected.",
        )

    lessons: list[LessonEntry] = []
    if occurrences is not None:
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
    else:
        # No real timetable — teacher-declared placeholder lessons,
        # identified by position rather than a real calendar/period.
        for i, body in enumerate(result.lessons):
            lessons.append(LessonEntry(
                sequence_index=i + 1, introduction=body.introduction,
                main_lesson=body.main_lesson, closure=body.closure, delivery_status="DRAFT",
            ))

    content.lessons = lessons
    content.assessment = result.assessment
    content.occurrence_mismatch = False
    # content_standard (descriptive prose) first, not indicator (a terse GES
    # code like "B7.1.1.1" that essentially never appears verbatim in lesson
    # prose and would make the keyword-overlap check fire almost always).
    content.generation_warnings = validate_lessons(lessons, lp.content_standard or lp.indicator)
    lp.generated_content = content.model_dump(mode="json")
    sync_legacy_fields_from_content(lp, content)
    await db.flush()
    return _to_read(lp)


async def regenerate_lesson(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
    *, school_calendar_id: uuid.UUID | None = None, period_id: uuid.UUID | None = None,
    sequence_index: int | None = None,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    content = get_content(lp)
    if school_calendar_id is not None and period_id is not None:
        idx = next(
            (i for i, l in enumerate(content.lessons)
             if l.school_calendar_id == school_calendar_id and l.period_id == period_id),
            None,
        )
    elif sequence_index is not None:
        idx = next((i for i, l in enumerate(content.lessons) if l.sequence_index == sequence_index), None)
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide either (school_calendar_id and period_id) or sequence_index to identify the lesson.",
        )
    if idx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That lesson occurrence is not part of this plan.")

    driver, cfg = await get_ready_driver(school_id, user_id, db)

    existing = content.lessons[idx]
    context = await build_context(lp, school_id, db)
    if existing.lesson_date is not None:
        lesson_ref = (
            f"This specific lesson is on {existing.lesson_date.isoformat()}, "
            f"{existing.start_time}-{existing.end_time} ({existing.duration_minutes} minutes)."
        )
    else:
        lesson_ref = f"This is lesson {existing.sequence_index} of {len(content.lessons)} for the week (no confirmed date/time)."
    prompt = (
        f"{context}\n\n{lesson_ref} "
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
