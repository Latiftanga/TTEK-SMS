"""
Group 8 — Assessments, scores, grading scales, and behaviour records.

Tables in this group:
  grading_scale        — defines how raw scores map to letter grades (A1, B2, etc.)
  grade                — one band within a grading scale (e.g. 80-100 = A1)
  assessment_type      — category of assessment (class test, end-of-term, etc.)
  assessment           — a specific test or exam for a class+subject+term
  score                — a student's raw result for one assessment
  score_audit_log      — immutable log of every score change
  student_behaviour_record — discipline and conduct incidents

CRITICAL INVARIANT — Grade is NEVER stored on Score
-----------------------------------------------------
The letter grade (A1, B2, C4, etc.) for a score is computed at query time
by looking up the student's raw_score against the school's GradingScale.
It is NEVER stored as a column on the score row.

The ONLY exception is Score.cached_grade_label, which is a performance cache:
  - It is populated (set) when an admin approves the score.
  - It is cleared (set to NULL) if the school's GradingScale is ever changed.
  - It lets report cards display grades without a per-score JOIN to GradingScale.

If you add a feature that changes a GradingScale, you MUST also clear
cached_grade_label on all Score rows for that school.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, Date, DateTime, ForeignKey, Text, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, SchoolScopedMixin


class GradingScale(Base, UUIDPrimaryKey, TimestampMixin):
    """
    Grading scale definition. school_id is nullable — system defaults exist
    alongside school-specific overrides.
    """
    __tablename__ = "grading_scale"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    grades: Mapped[list[Grade]] = relationship(
        back_populates="grading_scale", cascade="all, delete-orphan", order_by="Grade.min_score.desc()"
    )


class Grade(Base, UUIDPrimaryKey):
    """
    A band within a GradingScale. Score → Grade resolved at query time.
    Grade is NEVER stored on Score directly.
    """
    __tablename__ = "grade"
    __table_args__ = (
        UniqueConstraint("grading_scale_id", "letter_grade", name="uq_grade_letter"),
    )

    grading_scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grading_scale.id", ondelete="CASCADE"), nullable=False, index=True
    )
    min_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    letter_grade: Mapped[str] = mapped_column(String(5), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    gpa_points: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(100), nullable=True)

    grading_scale: Mapped[GradingScale] = relationship(back_populates="grades")


class AssessmentType(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "assessment_type"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assessments: Mapped[list[Assessment]] = relationship(back_populates="assessment_type")


class Assessment(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "assessment"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False
    )
    assessment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_type.id"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    assessment_type: Mapped[AssessmentType] = relationship(back_populates="assessments")
    scores: Mapped[list[Score]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class Score(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """
    A student's raw score for one Assessment.

    APPROVAL FLOW
    1. Teacher enters raw_score → is_approved=False, cached_grade_label=NULL
    2. HOD/admin approves → is_approved=True, approved_by_id and approved_at stamped,
       cached_grade_label set from the school's GradingScale
    3. If GradingScale changes → cached_grade_label must be cleared for recalculation

    See module docstring for the full "Grade is never stored" invariant.
    """
    __tablename__ = "score"
    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="uq_score_assessment_student"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    cached_grade_label: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    entered_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assessment: Mapped[Assessment] = relationship(back_populates="scores")
    audit_logs: Mapped[list[ScoreAuditLog]] = relationship(back_populates="score", cascade="all, delete-orphan")


class ScoreAuditLog(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "score_audit_log"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("score.id", ondelete="CASCADE"), nullable=False, index=True
    )
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    old_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    new_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    score: Mapped[Score] = relationship(back_populates="audit_logs")


class StudentBehaviourRecord(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "student_behaviour_record"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False
    )
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
