"""AI-assisted lesson planning — generated_content, approval workflow, curriculum_standard

Revision ID: f1a2b3c4d5e6
Revises: d5e6f7a8b9c1
Create Date: 2026-08-30

Additive only — every existing lesson_plan column/row/test is untouched.
Adds:
  - lesson_plan.generated_content (JSONB) — AI-produced structured content,
    see schemas/lesson_plans.py::GeneratedContent.
  - lesson_plan.status/reviewed_by_staff_id/review_notes/reviewed_at — an
    approval workflow, reversing 12cp's original "no approval workflow"
    scoping decision.
  - lesson_plan.curriculum_standard_id — optional autofill source.
  - curriculum_standard — new table, starts empty. See models/lesson_plans.py
    for why school_id is nullable and there's no separate syllabus_source
    column.
  - lesson_plan_generation_log — audit trail of every AI generation call,
    mirrors assessment_audit_log's SET NULL (not CASCADE) shape.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "d5e6f7a8b9c1"
branch_labels = None
depends_on = None

_lessonplanstatus = postgresql.ENUM("DRAFT", "APPROVED", name="lessonplanstatus", create_type=False)
_generationstage = postgresql.ENUM(
    "SKELETON", "LESSONS", "REGENERATE_LESSON", "REGENERATE_ASSESSMENT",
    name="lessonplangenerationstage", create_type=False,
)


def upgrade() -> None:
    _lessonplanstatus.create(op.get_bind(), checkfirst=True)
    _generationstage.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "curriculum_standard",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("subject_catalogue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject_catalogue.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("year_group", sa.Integer, nullable=False),
        sa.Column("strand", sa.String(200), nullable=False),
        sa.Column("sub_strand", sa.String(200), nullable=False),
        sa.Column("indicator_code", sa.String(50), nullable=False),
        sa.Column("objective_text", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_curriculum_standard_scope_subject_indicator",
        "curriculum_standard",
        ["subject_catalogue_id", "indicator_code", sa.text("coalesce(school_id, '00000000-0000-0000-0000-000000000000'::uuid)")],
        unique=True,
    )

    op.add_column("lesson_plan", sa.Column("curriculum_standard_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("curriculum_standard.id"), nullable=True))
    op.add_column("lesson_plan", sa.Column("generated_content", postgresql.JSONB, nullable=True))
    op.add_column("lesson_plan", sa.Column("status", _lessonplanstatus, nullable=False, server_default="DRAFT"))
    op.add_column("lesson_plan", sa.Column("reviewed_by_staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_member.id", ondelete="SET NULL"), nullable=True))
    op.add_column("lesson_plan", sa.Column("review_notes", sa.Text, nullable=True))
    op.add_column("lesson_plan", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "lesson_plan_generation_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("lesson_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lesson_plan.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("stage", _generationstage, nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("model_provider", sa.String(30), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("created_by_staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_member.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lesson_plan_generation_log")
    op.drop_column("lesson_plan", "reviewed_at")
    op.drop_column("lesson_plan", "review_notes")
    op.drop_column("lesson_plan", "reviewed_by_staff_id")
    op.drop_column("lesson_plan", "status")
    op.drop_column("lesson_plan", "generated_content")
    op.drop_column("lesson_plan", "curriculum_standard_id")
    op.drop_index("uq_curriculum_standard_scope_subject_indicator", table_name="curriculum_standard")
    op.drop_table("curriculum_standard")
    _generationstage.drop(op.get_bind(), checkfirst=True)
    _lessonplanstatus.drop(op.get_bind(), checkfirst=True)
