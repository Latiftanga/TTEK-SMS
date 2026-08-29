"""Lesson plan

Revision ID: 355c4338994d
Revises: 35eba42e429d
Create Date: 2026-08-19

Adds lesson_plan — a personal weekly planner for subject teachers. One row
per (class, subject, week_start_date); no approval workflow, scoped the
same way as Assessments (core/teacher_scope.py::resolve_assessment_scope).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "355c4338994d"
down_revision = "35eba42e429d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_plan",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_term_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("academic_term.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start_date", sa.Date, nullable=False),
        sa.Column("topic", sa.String(300), nullable=False),
        sa.Column("content_standard", sa.String(300), nullable=True),
        sa.Column("indicator", sa.String(300), nullable=True),
        sa.Column("learning_objectives", sa.Text, nullable=True),
        sa.Column("core_competencies", sa.String(300), nullable=True),
        sa.Column("teaching_resources", sa.Text, nullable=True),
        sa.Column("activities", sa.Text, nullable=True),
        sa.Column("assessment_strategy", sa.Text, nullable=True),
        sa.Column("reflection_notes", sa.Text, nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("class_id", "subject_id", "week_start_date", name="uq_lesson_plan_week"),
    )


def downgrade() -> None:
    op.drop_table("lesson_plan")
