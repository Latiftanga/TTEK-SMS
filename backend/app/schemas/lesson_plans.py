from __future__ import annotations
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.models.lesson_plans import ChatMessageRole, LessonPlanStatus


class LessonPlanCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    week_start_date: date  # any date in the target week — normalized server-side
    topic: str = Field(min_length=1, max_length=300)
    # No max_length: a real extracted indicator/content-standard sentence
    # (autofilled from a CurriculumUnit) can run well past what a short
    # manual entry would — matches learning_objectives' own unbounded Text.
    content_standard: str | None = None
    indicator: str | None = None
    learning_objectives: str | None = None
    core_competencies: str | None = Field(default=None, max_length=300)
    teaching_resources: str | None = None
    activities: str | None = None
    assessment_strategy: str | None = None
    reflection_notes: str | None = None
    # Optional autofill source — when set, content_standard/indicator/
    # learning_objectives are filled server-side from the linked
    # CurriculumStandard row if the caller left them blank.
    curriculum_standard_id: uuid.UUID | None = None
    # A second, independent optional autofill source — a specific
    # machine-extracted CurriculumUnit the teacher picked from a short
    # list. Also fills strand/sub_strand, which curriculum_standard_id
    # alone does not carry. See services/lesson_plans.py::_resolve_curriculum_unit.
    curriculum_unit_id: uuid.UUID | None = None


class LessonPlanUpdate(BaseModel):
    topic: str | None = Field(default=None, min_length=1, max_length=300)
    content_standard: str | None = None
    indicator: str | None = None
    learning_objectives: str | None = None
    core_competencies: str | None = Field(default=None, max_length=300)
    teaching_resources: str | None = None
    activities: str | None = None
    assessment_strategy: str | None = None
    reflection_notes: str | None = None
    curriculum_standard_id: uuid.UUID | None = None
    curriculum_unit_id: uuid.UUID | None = None


# ── AI-generated structured content ─────────────────────────────────────────
# Stored as LessonPlan.generated_content (JSONB). Every field here is
# AI-produced; the plan's own scalar columns (topic, activities,
# assessment_strategy, reflection_notes, ...) are untouched by any of it.

class LessonPlanSkeleton(BaseModel):
    """Cheap-to-iterate first pass — produced by generate-skeleton, editable
    by the teacher before approving into generate-lessons. content_standard/
    indicator/learning_objectives are the AI's proposed GES curriculum
    reference for this topic — a teacher never has to type these
    themselves; see services/lesson_plan_prompt.py::propose_curriculum_reference()
    for how they're grounded."""
    essential_questions: list[str] = Field(default_factory=list)
    pedagogical_strategies: list[str] = Field(default_factory=list)
    teaching_learning_resources: list[str] = Field(default_factory=list)
    differentiation_notes: str | None = None
    content_standard: str | None = None
    indicator: str | None = None
    learning_objectives: str | None = None


class CurriculumReferenceSuggestion(BaseModel):
    """LLM-facing shape for the chat path's first-message curriculum-
    reference proposal — the same three fields as LessonPlanSkeleton's own,
    factored out since the chat path has no other structured call to bundle
    them into."""
    content_standard: str | None = None
    indicator: str | None = None
    learning_objectives: str | None = None


class LessonEntry(BaseModel):
    """One per real scheduled occurrence that week — see
    services/lesson_plan_occurrences.py::resolve_week_occurrences(). Identity
    (school_calendar_id, period_id) is captured at generation time so a later
    re-open can detect if the timetable has since changed underneath it.
    delivery_status is named distinctly from LessonPlan.status (the plan-level
    approval workflow) to avoid the spec's two different "status" concepts
    colliding.

    school_calendar_id/period_id/lesson_date/start_time/end_time/
    duration_minutes are all nullable together — a class with no real
    timetable configured for this class+subject+week has no real calendar
    day/period to attach to at all (see
    services/lesson_plan_occurrences.py::get_occurrences_or_require_count).
    Such a lesson is a teacher-declared placeholder identified instead by
    sequence_index (its 1-based position within the plan's lessons list) —
    regenerate_lesson looks it up by whichever identity is present."""
    school_calendar_id: uuid.UUID | None = None
    period_id: uuid.UUID | None = None
    sequence_index: int | None = None
    lesson_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = None
    introduction: str
    main_lesson: str
    closure: str
    delivery_status: str = "DRAFT"  # DRAFT | APPROVED | TAUGHT


class AssessmentSection(BaseModel):
    mode: str
    task: str


class FormativeAssessment(AssessmentSection):
    mark_scheme: str


class TranscriptAssessment(AssessmentSection):
    rubric: str


class AssessmentBlock(BaseModel):
    formative: FormativeAssessment
    transcript_assessment: TranscriptAssessment


class GeneratedContent(BaseModel):
    essential_questions: list[str] = Field(default_factory=list)
    pedagogical_strategies: list[str] = Field(default_factory=list)
    teaching_learning_resources: list[str] = Field(default_factory=list)
    differentiation_notes: str | None = None
    lessons: list[LessonEntry] = Field(default_factory=list)
    assessment: AssessmentBlock | None = None
    # Populated by generate-lessons/review when a stored occurrence no longer
    # matches a fresh resolve_week_occurrences() call (timetable changed, a
    # day became a holiday, ...) — surfaced to the teacher, never silently
    # auto-applied.
    occurrence_mismatch: bool = False
    # Best-effort validation-pass output (time-budget/indicator sanity
    # checks) — informational, never blocks generation itself.
    generation_warnings: list[str] = Field(default_factory=list)


# ── LLM-facing shapes only (never returned directly to the client) ─────────
# The model is never asked to invent our internal UUIDs — the service zips
# its ordered response against resolve_week_occurrences()'s real identities.

class LessonBody(BaseModel):
    introduction: str
    main_lesson: str
    closure: str


class GeneratedLessonsResponse(BaseModel):
    lessons: list[LessonBody]
    assessment: AssessmentBlock


class LessonPlanRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    week_start_date: date
    topic: str
    content_standard: str | None
    indicator: str | None
    learning_objectives: str | None
    core_competencies: str | None
    teaching_resources: str | None
    activities: str | None
    assessment_strategy: str | None
    reflection_notes: str | None
    strand: str | None
    sub_strand: str | None
    created_by_id: uuid.UUID
    curriculum_standard_id: uuid.UUID | None
    curriculum_unit_id: uuid.UUID | None
    generated_content: GeneratedContent | None
    status: LessonPlanStatus
    reviewed_by_staff_id: uuid.UUID | None
    review_notes: str | None
    reviewed_at: datetime | None
    model_config = {"from_attributes": True}


class LessonPlanReviewRequest(BaseModel):
    status: LessonPlanStatus
    review_notes: str | None = None


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageRead(BaseModel):
    id: uuid.UUID
    role: ChatMessageRole
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


class RegenerateLessonRequest(BaseModel):
    """Either (school_calendar_id, period_id) for a real-occurrence lesson,
    or sequence_index for a teacher-declared (no-timetable) placeholder —
    see LessonEntry's own docstring."""
    school_calendar_id: uuid.UUID | None = None
    period_id: uuid.UUID | None = None
    sequence_index: int | None = None


class GenerateLessonsRequest(BaseModel):
    """lesson_count is only consulted when the class+subject genuinely has
    no real timetable data for this week (resolve_week_occurrences returns
    none) — whenever a real timetable exists, its count stays authoritative
    and this is ignored, never an override."""
    lesson_count: int | None = Field(default=None, ge=1, le=20)


class FinalizeChatRequest(BaseModel):
    lesson_count: int | None = Field(default=None, ge=1, le=20)


class LessonPlanAiDraftRequest(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    topic: str = Field(min_length=1, max_length=300)


class LessonPlanAiDraftResponse(BaseModel):
    draft_text: str


# ── Curriculum standards ─────────────────────────────────────────────────────

class CurriculumStandardCreate(BaseModel):
    subject_catalogue_id: uuid.UUID
    level: str = Field(min_length=1, max_length=20)
    year_group: int = Field(ge=1)
    strand: str = Field(min_length=1, max_length=200)
    sub_strand: str = Field(min_length=1, max_length=200)
    indicator_code: str = Field(min_length=1, max_length=50)
    objective_text: str = Field(min_length=1)


class CurriculumStandardRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID | None
    subject_catalogue_id: uuid.UUID
    level: str
    year_group: int
    strand: str
    sub_strand: str
    indicator_code: str
    objective_text: str
    is_active: bool
    model_config = {"from_attributes": True}
