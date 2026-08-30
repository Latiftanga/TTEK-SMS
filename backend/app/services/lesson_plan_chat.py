"""
Curriculum-grounded chat assistant — the real back-and-forth interaction
mode for lesson planning, additive alongside the existing button-driven
generate-skeleton/generate-lessons/regenerate-* flow (services/
lesson_plan_generation.py). A teacher converses freely; "finalize" converts
the conversation into the same GeneratedContent shape (lessons[] +
assessment) generate_lessons() already produces, so review/approval and
everything downstream works identically regardless of which path built the
plan.

Each turn re-runs full-text search (services/curriculum_search.py) keyed on
the plan's topic + the latest message, so retrieval adapts as the
conversation evolves rather than being fixed once at session start.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import year_for_term
from app.models.lesson_plans import ChatMessageRole, LessonPlanChatMessage, LessonPlanGenerationStage
from app.schemas.lesson_plans import ChatMessageRead, GeneratedLessonsResponse, LessonEntry, LessonPlanRead
from app.services import ai_config
from app.services.ai_driver import generate_json
from app.services.lesson_plan_occurrences import resolve_week_occurrences
from app.services.lesson_plan_prompt import (
    apply_curriculum_reference, build_context, get_curriculum_excerpts,
    get_ready_driver, get_content, log_generation, propose_curriculum_reference, validate_lessons,
)
from app.services.lesson_plans import _to_read, get_lesson_plan

_CHAT_GUARDRAILS = (
    "You are a curriculum-grounded lesson-planning assistant for a Ghanaian "
    "teacher. Ground your answers in the curriculum excerpts provided below "
    "when they're relevant, and cite the source (document name + page "
    "number) when you draw on them. If nothing relevant was retrieved, say "
    "so plainly rather than inventing a citation. Be concrete and "
    "classroom-practical. This is a conversation — respond to what the "
    "teacher actually asked, don't just restate the whole lesson plan every turn."
)


def _to_message_read(m: LessonPlanChatMessage) -> ChatMessageRead:
    return ChatMessageRead.model_validate(m)


async def _load_messages(lesson_plan_id: uuid.UUID, db: AsyncSession) -> list[LessonPlanChatMessage]:
    return list(await db.scalars(
        select(LessonPlanChatMessage)
        .where(LessonPlanChatMessage.lesson_plan_id == lesson_plan_id)
        .order_by(LessonPlanChatMessage.created_at)
    ))


def _transcript(messages: list[LessonPlanChatMessage]) -> str:
    speaker = {ChatMessageRole.USER: "Teacher", ChatMessageRole.ASSISTANT: "Assistant"}
    return "\n".join(f"{speaker[m.role]}: {m.content}" for m in messages)


async def send_chat_message(
    lesson_plan_id: uuid.UUID, message_text: str,
    school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> list[ChatMessageRead]:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    driver, cfg = await get_ready_driver(school_id, user_id, db)

    # On the very first turn of a conversation, also propose the content
    # standard/indicator/learning objectives — a teacher never has to type
    # these themselves regardless of whether they use chat or the buttons.
    # A genuinely separate AI call (unlike the skeleton path, chat has no
    # other structured call to bundle it into) — see propose_curriculum_reference()'s
    # own docstring. Deliberately fail-soft: this is a nice-to-have on top of
    # the conversation, not something that should break the actual chat
    # reply below if the model's response can't be parsed as JSON.
    is_first_turn = not await _load_messages(lp.id, db)
    if is_first_turn:
        try:
            suggestion = await propose_curriculum_reference(lp, school_id, driver, db)
        except HTTPException:
            suggestion = None
        if suggestion:
            apply_curriculum_reference(lp, suggestion)
            await log_generation(
                school_id, lp.id, LessonPlanGenerationStage.CHAT, "(curriculum reference proposal)",
                cfg.provider.value, cfg.model or "default", staff_id, db,
            )
            await ai_config.increment_usage(school_id, user_id, cfg)

    now = datetime.now(timezone.utc)
    db.add(LessonPlanChatMessage(
        school_id=school_id, lesson_plan_id=lp.id, role=ChatMessageRole.USER,
        content=message_text, created_at=now,
    ))
    await db.flush()

    excerpts = await get_curriculum_excerpts(lp.class_id, lp.subject_id, f"{lp.topic} {message_text}", school_id, db)
    context = await build_context(lp, school_id, db)
    messages = await _load_messages(lp.id, db)
    prompt = (
        f"{context}\n\nRelevant curriculum excerpts:\n{excerpts}\n\n"
        f"Conversation so far:\n{_transcript(messages)}\n\nAssistant:"
    )
    reply_text = await driver.generate(prompt, _CHAT_GUARDRAILS)

    db.add(LessonPlanChatMessage(
        school_id=school_id, lesson_plan_id=lp.id, role=ChatMessageRole.ASSISTANT,
        content=reply_text, created_at=datetime.now(timezone.utc),
    ))
    await log_generation(
        school_id, lp.id, LessonPlanGenerationStage.CHAT, prompt,
        cfg.provider.value, cfg.model or "default", staff_id, db,
    )
    await ai_config.increment_usage(school_id, user_id, cfg)
    await db.flush()

    return [_to_message_read(m) for m in await _load_messages(lp.id, db)]


async def list_chat_messages(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> list[ChatMessageRead]:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    return [_to_message_read(m) for m in await _load_messages(lp.id, db)]


async def finalize_chat(
    lesson_plan_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    lp = await get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    messages = await _load_messages(lp.id, db)
    if not messages:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Start a conversation first.")

    year_id = await year_for_term(lp.academic_term_id, db)
    if year_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Academic term has no year.")
    week_end = lp.week_start_date + timedelta(days=6)
    occurrences = await resolve_week_occurrences(lp.class_id, lp.subject_id, year_id, lp.week_start_date, week_end, school_id, db)
    if not occurrences:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No real scheduled occurrences found for this class/subject this week "
            "(check the timetable and calendar for that week).",
        )

    driver, cfg = await get_ready_driver(school_id, user_id, db)
    context = await build_context(lp, school_id, db)
    occ_lines = "\n".join(f"- {o.lesson_date.isoformat()}, {o.start_time}-{o.end_time}" for o in occurrences)
    prompt = (
        f"{context}\n\nConversation with the teacher so far:\n{_transcript(messages)}\n\n"
        f"There are exactly {len(occurrences)} scheduled lessons this week:\n{occ_lines}\n\n"
        f"Based on everything discussed above, produce exactly {len(occurrences)} lesson entries in "
        "the same order as listed above (introduction, main lesson, closure for each), sized to fit "
        "each lesson's own duration. Also produce one assessment block: a formative check (mode, "
        "task, mark scheme) and a transcript/summative assessment (mode, task, rubric)."
    )
    result = await generate_json(driver, prompt, _CHAT_GUARDRAILS, GeneratedLessonsResponse)
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
        duration = (occ.end_time.hour * 60 + occ.end_time.minute) - (occ.start_time.hour * 60 + occ.start_time.minute)
        lessons.append(LessonEntry(
            school_calendar_id=occ.school_calendar_id, period_id=occ.period_id,
            lesson_date=occ.lesson_date, start_time=occ.start_time, end_time=occ.end_time,
            duration_minutes=duration, introduction=body.introduction,
            main_lesson=body.main_lesson, closure=body.closure, delivery_status="DRAFT",
        ))

    content = get_content(lp)
    content.lessons = lessons
    content.assessment = result.assessment
    content.occurrence_mismatch = False
    content.generation_warnings = validate_lessons(lessons, lp.indicator or lp.content_standard)
    lp.generated_content = content.model_dump(mode="json")
    await db.flush()
    return _to_read(lp)
