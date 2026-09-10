"""
Single-shot AI draft (POST /lesson-plans/ai-draft) — split out of
services/lesson_plans.py to stay under the 300-line cap. Distinct from the
staged skeleton/generate-lessons flow (services/lesson_plan_generation.py)
and the full conversational chat (services/lesson_plan_chat.py): this is a
one-shot, non-conversational draft, kept for a teacher who wants a quick
starting point without either of those.
"""
from __future__ import annotations
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme, Subject
from app.services import ai_config
from app.services.ai_driver import generate_safe
from app.services.student_display import _class_display_name

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
    individual fields. Falls back to the platform-default provider if this
    school hasn't configured its own (see ai_config.py::
    resolve_driver_for_generation)."""
    driver, cfg = await ai_config.resolve_driver_for_generation(school_id, db)  # raises 503 if neither exists
    await ai_config.check_daily_limit(school_id, user_id, cfg, db)  # raises 429 if exhausted

    subject = await db.get(Subject, subject_id)
    cls = await db.get(Class, class_id)
    prog_name = None
    if cls and cls.programme_id:
        prog = await db.get(SHSProgramme, cls.programme_id)
        prog_name = prog.name if prog else None
    class_label = _class_display_name(cls.level, cls.year_group, prog_name, cls.stream) if cls else "the class"
    subject_name = subject.name if subject else "the subject"

    prompt = f"Draft a weekly lesson plan for {class_label}, subject: {subject_name}. Topic: {topic}."
    draft_text = await generate_safe(driver, prompt, _AI_SYSTEM_PROMPT)

    await ai_config.increment_usage(school_id, user_id, cfg)
    return draft_text
