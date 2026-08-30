"""
Lesson planner — a personal weekly planning tool for subject teachers.

One LessonPlan per (class, subject, week) — the traditional GES "weekly
forecast" format, not a per-single-lesson record. week_start_date is always
normalized to that week's Monday (see services/lesson_plans.py) so the
frontend and backend never disagree about which week a date belongs to.

Approval workflow (status/reviewed_by/review_notes/reviewed_at): a teacher
creates/edits their own plans, scoped by SubjectTeacher assignment exactly
like Assessments (core/teacher_scope.py::resolve_assessment_scope). Review is
gated on the narrow lesson_plans.approve permission (granted to HEAD by
default, grantable to anyone else via a personal permission override) —
distinct from lesson_plans.manage, the plan-owner's own tier, mirroring the
assessments.record_behaviour/approve_scores split from 12am. A reviewer still
needs resolve_assessment_scope's existing assessments.approve_scores-holder
bypass to see/act on a plan outside their own SubjectTeacher assignments —
lesson_plans.approve alone only clears the router gate, same
necessary-but-insufficient shape used everywhere else in this codebase.

generated_content (JSONB) holds AI-produced structured content (skeleton
fields, per-occurrence lessons, the assessment block) — see
schemas/lesson_plans.py::GeneratedContent. Every existing scalar column below
(topic, content_standard, activities, ...) is untouched by AI generation and
stays exactly as the manual/legacy fields for a teacher who never uses it.
reflection_notes in particular is teacher-only, written after the lesson is
taught, and is never touched by any generation endpoint.
"""
from __future__ import annotations
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class LessonPlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class LessonPlanGenerationStage(str, enum.Enum):
    SKELETON = "SKELETON"
    LESSONS = "LESSONS"
    REGENERATE_LESSON = "REGENERATE_LESSON"
    REGENERATE_ASSESSMENT = "REGENERATE_ASSESSMENT"
    CHAT = "CHAT"


class ChatMessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class LessonPlan(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "lesson_plan"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", "week_start_date", name="uq_lesson_plan_week"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject.id", ondelete="CASCADE"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id", ondelete="CASCADE"), nullable=False
    )
    # Always a Monday — see services/lesson_plans.py::_normalize_week_start().
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)

    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    # GES-style curriculum reference fields — free text, since no linked
    # curriculum/strand data model exists in this codebase to validate
    # against (SubjectCatalogue is just a name/code/type/level catalogue).
    content_standard: Mapped[str | None] = mapped_column(String(300), nullable=True)
    indicator: Mapped[str | None] = mapped_column(String(300), nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Comma-separated GES core-competency tags (Communication & Collaboration,
    # Critical Thinking, Creativity & Innovation, Digital Literacy, Personal
    # Development & Leadership) — offered as checkboxes client-side, stored
    # as a single text field rather than a separate table for this v1.
    core_competencies: Mapped[str | None] = mapped_column(String(300), nullable=True)
    teaching_resources: Mapped[str | None] = mapped_column(Text, nullable=True)
    activities: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Filled in after the lesson is actually taught — optional, never
    # required at creation time. Never touched by AI generation.
    reflection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False
    )

    # Optional autofill source for content_standard/indicator/learning_objectives.
    # Nullable, no FK ondelete cascade — CurriculumStandard rows are retired
    # (is_active=False), never hard-deleted, so there's nothing to react to.
    curriculum_standard_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_standard.id"), nullable=True
    )

    # AI-generated structured content — see schemas/lesson_plans.py::GeneratedContent.
    # Nullable: a plan with no AI generation ever run just has this as None.
    generated_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Approval workflow — see module docstring.
    status: Mapped[LessonPlanStatus] = mapped_column(
        SAEnum(LessonPlanStatus, name="lessonplanstatus"), nullable=False, default=LessonPlanStatus.DRAFT,
    )
    reviewed_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="SET NULL"), nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CurriculumStandard(Base, UUIDPrimaryKey, TimestampMixin):
    """
    GES-style curriculum reference (strand/sub-strand/indicator) used to
    autofill LessonPlan.content_standard/indicator/learning_objectives.
    Nullable school_id mirrors SubjectCatalogue exactly — a shared,
    system-wide GES row (school_id=NULL) vs. a school's own private-syllabus
    row — so no separate syllabus_source column is needed, it's implied by
    school_id. Starts empty; seeded incrementally (admin data entry, or a
    later GES-data seed script — not this pass). Deliberately not a hard
    dependency: LessonPlan.curriculum_standard_id is optional, a plan can
    still be created with free-text content_standard/indicator if nothing
    here matches yet.
    """
    __tablename__ = "curriculum_standard"
    __table_args__ = (
        # COALESCE'd rather than a plain UniqueConstraint because school_id
        # is nullable and Postgres treats NULL != NULL in a plain unique
        # constraint — same pattern as Class's own school-scoped uniqueness.
        Index(
            "uq_curriculum_standard_scope_subject_indicator",
            "subject_catalogue_id", "indicator_code",
            text("coalesce(school_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    subject_catalogue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject_catalogue.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Mirrors Class.level/year_group exactly, so autofill can match a
    # specific class precisely (e.g. level="SHS", year_group=2).
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    year_group: Mapped[int] = mapped_column(Integer, nullable=False)
    strand: Mapped[str] = mapped_column(String(200), nullable=False)
    sub_strand: Mapped[str] = mapped_column(String(200), nullable=False)
    indicator_code: Mapped[str] = mapped_column(String(50), nullable=False)
    objective_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LessonPlanGenerationLog(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Immutable log of every AI generation call against a LessonPlan —
    mirrors ScoreAuditLog/AssessmentAuditLog/BehaviourAuditLog. lesson_plan_id
    is SET NULL (not CASCADE) so the log survives the plan it documents.
    """
    __tablename__ = "lesson_plan_generation_log"

    lesson_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_plan.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    stage: Mapped[LessonPlanGenerationStage] = mapped_column(
        SAEnum(LessonPlanGenerationStage, name="lessonplangenerationstage"), nullable=False,
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LessonPlanChatMessage(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    One conversation per LessonPlan — the curriculum-grounded chat assistant.
    lesson_plan_id is CASCADE (not SET NULL, unlike the generation log): a
    conversation has no meaning detached from the plan it was building
    towards, unlike an audit-trail row that must outlive what it documents.
    """
    __tablename__ = "lesson_plan_chat_message"

    lesson_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_plan.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    role: Mapped[ChatMessageRole] = mapped_column(
        SAEnum(ChatMessageRole, name="chatmessagerole"), nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
