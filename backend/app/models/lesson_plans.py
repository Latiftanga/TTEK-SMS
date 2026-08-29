"""
Lesson planner — a personal weekly planning tool for subject teachers.

One LessonPlan per (class, subject, week) — the traditional GES "weekly
forecast" format, not a per-single-lesson record. week_start_date is always
normalized to that week's Monday (see services/lesson_plans.py) so the
frontend and backend never disagree about which week a date belongs to.

No approval workflow (deliberately, per this feature's own scoping decision):
a teacher creates/edits their own plans, scoped by SubjectTeacher assignment
exactly like Assessments (core/teacher_scope.py::resolve_assessment_scope).
Senior staff (assessments.approve_scores holders) see/manage every plan for
oversight, same bypass convention as everywhere else in this codebase — no
separate "reviewer" role needed.
"""
from __future__ import annotations
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


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
    # required at creation time.
    reflection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False
    )
