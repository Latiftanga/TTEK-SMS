"""
Shared helpers for services/lesson_plan_generation.py — prompt context
building, AI driver resolution, generation-log writes, and the post-
generation validation pass. Split out purely to keep
lesson_plan_generation.py's orchestration functions under the 300-line cap,
same pattern as report_card_scoring.py being a shared leaf module for
report_card.py/report_card_rank.py.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassSubject, SHSProgramme, Subject
from app.models.lesson_plans import LessonPlan, LessonPlanGenerationLog, LessonPlanGenerationStage
from app.models.school import AiConfig
from app.models.students import StudentClassAssignment
from app.schemas.lesson_plans import CurriculumReferenceSuggestion, GeneratedContent, LessonEntry
from app.services import ai_config
from app.services.ai_driver import AiDriver, generate_json
from app.services.curriculum_search import search_curriculum
from app.services.student_display import _class_display_name

SYSTEM_GUARDRAILS = (
    "You are an assistant helping a Ghanaian teacher plan lessons aligned "
    "with the GES Standards-Based Curriculum. Be concrete and classroom-"
    "practical, never generic filler. Never fabricate a curriculum "
    "indicator or standard that wasn't given to you — work only from the "
    "context provided."
)


def get_content(lp: LessonPlan) -> GeneratedContent:
    return GeneratedContent.model_validate(lp.generated_content) if lp.generated_content else GeneratedContent()


def sync_legacy_fields_from_content(lp: LessonPlan, content: GeneratedContent) -> None:
    """Keeps LessonPlan's own legacy scalar fields (teaching_resources/
    activities/assessment_strategy — the "Plan details" panel's manual
    fields) as a readable summary of the AI-generated content, populated
    only the first time each becomes available and never overwritten again
    — the same "never clobber a value that's already set" rule already
    used for content_standard/indicator/learning_objectives (see
    services/lesson_plans.py::create_lesson_plan/update_lesson_plan).
    Without this, a teacher using chat/generation exclusively would see
    Plan details' fields sitting permanently blank even though a real,
    complete plan exists — confusing, reported directly."""
    if not lp.teaching_resources and content.teaching_learning_resources:
        lp.teaching_resources = "\n".join(f"- {r}" for r in content.teaching_learning_resources)
    if not lp.activities and content.lessons:
        lp.activities = "\n\n".join(
            f"{l.lesson_date.isoformat() if l.lesson_date else f'Lesson {l.sequence_index}'}: {l.main_lesson}"
            for l in content.lessons
        )
    if not lp.assessment_strategy and content.assessment:
        a = content.assessment
        lp.assessment_strategy = (
            f"Formative ({a.formative.mode}): {a.formative.task} — {a.formative.mark_scheme}\n"
            f"Summative ({a.transcript_assessment.mode}): {a.transcript_assessment.task} — {a.transcript_assessment.rubric}"
        )


async def build_context(
    lp: LessonPlan, school_id: uuid.UUID, db: AsyncSession, *,
    query_text: str | None = None, cs_id: uuid.UUID | None = None,
) -> str:
    """Shared by every generation/chat call site. Always includes the
    school's real uploaded curriculum excerpts (keyed on `query_text`,
    defaulting to the plan's own topic) — every stage that produces actual
    lesson/assessment content, not just generate_skeleton's one-time
    standard/indicator proposal, needs to be grounded in what was uploaded.

    Pass `cs_id` when the caller already resolved it (e.g. alongside its own
    propose_curriculum_reference() call on the same class+subject) to skip a
    redundant ClassSubject lookup.

    A single AsyncSession can't run concurrent queries (no asyncio.gather
    here — SQLAlchemy async sessions aren't safe for that), so this is
    written to minimize round trips instead: Class+SHSProgramme is one
    outerjoin (same pattern as core/teacher_scope.py::classes_for_scope),
    and the class-size count folds in its own year-for-term lookup as a
    join rather than two sequential calls."""
    subject = await db.get(Subject, lp.subject_id)

    cls_row = (await db.execute(
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(Class.id == lp.class_id)
    )).first()
    cls, prog_name = cls_row if cls_row else (None, None)
    class_label = _class_display_name(cls.level, cls.year_group, prog_name, cls.stream) if cls else "the class"
    subject_name = subject.name if subject else "the subject"

    # Folds year_for_term()'s own AcademicTerm lookup into the count query
    # itself — a missing/unset term yields no join match, so size stays 0,
    # same as the two-step "year_id = year_for_term(...); size = ... if
    # year_id else 0" this replaces.
    size = await db.scalar(
        select(func.count()).select_from(StudentClassAssignment)
        .join(AcademicTerm, AcademicTerm.academic_year_id == StudentClassAssignment.academic_year_id)
        .where(
            AcademicTerm.id == lp.academic_term_id,
            StudentClassAssignment.class_id == lp.class_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ) or 0

    recent = list(await db.scalars(
        select(LessonPlan.topic).where(
            LessonPlan.school_id == school_id, LessonPlan.class_id == lp.class_id,
            LessonPlan.subject_id == lp.subject_id, LessonPlan.id != lp.id,
        ).order_by(LessonPlan.week_start_date.desc()).limit(2)
    ))

    lines = [
        f"Class: {class_label}", f"Subject: {subject_name}",
        f"Number of learners: {size}" if size else "Number of learners: unknown",
        f"Week starting: {lp.week_start_date.isoformat()}",
        f"Topic: {lp.topic}",
    ]
    if lp.content_standard:
        lines.append(f"Content standard: {lp.content_standard}")
    if lp.indicator:
        lines.append(f"Learning indicator: {lp.indicator}")
    if lp.learning_objectives:
        lines.append(f"Learning objectives: {lp.learning_objectives}")
    if lp.core_competencies:
        lines.append(f"Core competencies to weave in: {lp.core_competencies}")
    if recent:
        lines.append(f"Recent topics taught to this class in this subject: {'; '.join(recent)}")

    excerpts = await get_curriculum_excerpts(lp.class_id, lp.subject_id, query_text or lp.topic, school_id, db, cs_id=cs_id)
    lines.append(f"Curriculum excerpts (ground your answer in these when relevant, cite document + page):\n{excerpts}")
    return "\n".join(lines)


async def log_generation(
    school_id: uuid.UUID, lesson_plan_id: uuid.UUID, stage: LessonPlanGenerationStage,
    prompt_text: str, provider: str, model_name: str, staff_id: uuid.UUID, db: AsyncSession,
) -> None:
    db.add(LessonPlanGenerationLog(
        school_id=school_id, lesson_plan_id=lesson_plan_id, stage=stage,
        prompt_text=prompt_text, model_provider=provider, model_name=model_name,
        created_by_staff_id=staff_id, created_at=datetime.now(timezone.utc),
    ))


async def get_ready_driver(
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> tuple[AiDriver, AiConfig]:
    """Resolves a usable driver — the school's own active config, falling
    back to the platform default (see ai_config.py) — and enforces the
    daily-limit check before returning it. Callers generate, then call
    ai_config.increment_usage(school_id, user_id, cfg) once done."""
    driver, cfg = await ai_config.resolve_driver_for_generation(school_id, db)
    await ai_config.check_daily_limit(school_id, user_id, cfg, db)
    return driver, cfg


_REFERENCE_GUARDRAILS = (
    "You are helping identify the correct GES (Ghana Education Service) curriculum "
    "reference for a lesson topic. If the curriculum excerpts below include an "
    "explicit content standard, indicator code, or learning objective for this "
    "topic, use that exact wording/code — never invent one that wasn't given to "
    "you. If nothing relevant was retrieved, give your best general estimate "
    "based on standard GES curriculum structure for this subject and grade level."
)


async def class_subject_id(class_id: uuid.UUID, subject_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    return await db.scalar(
        select(ClassSubject.id).where(
            ClassSubject.class_id == class_id, ClassSubject.subject_id == subject_id, ClassSubject.school_id == school_id,
        )
    )


async def get_curriculum_excerpts(
    class_id: uuid.UUID, subject_id: uuid.UUID, query_text: str, school_id: uuid.UUID, db: AsyncSession,
    *, cs_id: uuid.UUID | None = None,
) -> str:
    """Real, uploaded-material excerpts relevant to `query_text` (usually a
    lesson topic or the latest chat message) — grounds a generation/chat
    prompt in the school's own curriculum content instead of generic
    knowledge. Falls back to a plain "nothing found" note, not a blank
    string, so the model is told explicitly rather than left to guess why
    no excerpts appeared.

    Pass `cs_id` when the caller already resolved it (e.g. two excerpt
    lookups on the same class+subject in one request) to skip a redundant
    ClassSubject lookup — omit it to have this resolve it itself."""
    if cs_id is None:
        cs_id = await class_subject_id(class_id, subject_id, school_id, db)
    chunks = await search_curriculum(cs_id, query_text, school_id, db) if cs_id else []
    return "\n\n".join(
        f'[{c.document_type} "{c.file_name}", p.{c.page_number}]\n{c.chunk_text}' for c in chunks
    ) or "(No matching curriculum material was found for this — answer from general best practice, and say so.)"


async def propose_curriculum_reference(
    lp: LessonPlan, school_id: uuid.UUID, driver: AiDriver, db: AsyncSession,
    *, cs_id: uuid.UUID | None = None,
) -> CurriculumReferenceSuggestion | None:
    """Proposes content_standard/indicator/learning_objectives so a teacher
    never has to type them — grounded in the class+subject's uploaded
    curriculum material when available, falling back to the model's own
    general GES knowledge otherwise. Returns None (no AI call made) if every
    field is already set — a teacher's own manual entry, or an earlier
    proposal, is never re-proposed or overwritten. Used by the chat path
    (services/lesson_plan_chat.py) as its own dedicated call — the
    button-driven skeleton path bundles the same idea into its own single
    generate_json() call instead (see generate_skeleton()).

    Pass `cs_id` when the caller will also call build_context()/
    get_curriculum_excerpts() again in the same request, to avoid resolving
    the same ClassSubject twice."""
    if lp.content_standard and lp.indicator and lp.learning_objectives:
        return None
    excerpts = await get_curriculum_excerpts(lp.class_id, lp.subject_id, lp.topic, school_id, db, cs_id=cs_id)
    prompt = f"Topic: {lp.topic}\n\nCurriculum excerpts:\n{excerpts}\n\nPropose the content standard, learning indicator, and learning objectives for this topic."
    return await generate_json(driver, prompt, _REFERENCE_GUARDRAILS, CurriculumReferenceSuggestion)


def apply_curriculum_reference(lp: LessonPlan, suggestion: CurriculumReferenceSuggestion | None) -> None:
    """Fills lp.content_standard/indicator/learning_objectives from an AI
    suggestion, only where the field is currently blank."""
    if not suggestion:
        return
    if not lp.content_standard and suggestion.content_standard:
        lp.content_standard = suggestion.content_standard
    if not lp.indicator and suggestion.indicator:
        lp.indicator = suggestion.indicator
    if not lp.learning_objectives and suggestion.learning_objectives:
        lp.learning_objectives = suggestion.learning_objectives


_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "students", "will", "be", "able", "learners", "learn", "learning",
}


def validate_lessons(lessons: list[LessonEntry], indicator_text: str | None) -> list[str]:
    """Best-effort validation pass — flags, never blocks. Time-budget check
    is a rough words-per-minute heuristic, not an exact reading-time model;
    the indicator check is a soft keyword-overlap sanity check, not a
    semantic one. A teacher-declared placeholder lesson (no real timetable —
    see LessonEntry's own docstring) has no lesson_date/duration_minutes, so
    the time-budget check is skipped for it and its label falls back to
    sequence_index."""
    warnings: list[str] = []
    keywords: set[str] = set()
    if indicator_text:
        keywords = {
            w.strip(".,()").lower() for w in indicator_text.split()
            if len(w) > 3 and w.strip(".,()").lower() not in _STOPWORDS
        }

    for lesson in lessons:
        label = lesson.lesson_date.isoformat() if lesson.lesson_date else f"Lesson {lesson.sequence_index}"
        combined = f"{lesson.introduction} {lesson.main_lesson} {lesson.closure}"
        word_count = len(combined.split())
        # ~130 words/minute of spoken narration, generous 1.5x buffer for
        # in-class activity time (not everything is a teacher monologue).
        if lesson.duration_minutes is not None:
            budget = lesson.duration_minutes * 130 * 1.5
            if word_count > budget:
                warnings.append(
                    f"{label}: content may be too long for a "
                    f"{lesson.duration_minutes}-minute lesson — review before teaching."
                )
        if keywords and not (keywords & set(combined.lower().split())):
            warnings.append(
                f"{label}: content doesn't obviously reference "
                "the stated indicator — worth a quick check."
            )
    return warnings
