"""Curriculum materials (grounding for AI lesson planning) + chat

Revision ID: c4d8e2f6a9b1
Revises: b3c9d7a1e5f2
Create Date: 2026-08-30

Adds:
  - curriculum_material — uploaded textbook/teacher-manual/syllabus PDFs,
    scoped per class_subject.
  - curriculum_material_chunk — per-page extracted text + a GIN-indexed
    tsvector for full-text search (no pgvector/embeddings — see the plan
    this was built from).
  - lesson_plan_chat_message — one conversation per LessonPlan.
  - LessonPlanGenerationStage gains a CHAT value.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4d8e2f6a9b1"
down_revision = "b3c9d7a1e5f2"
branch_labels = None
depends_on = None

_extractionstatus = postgresql.ENUM(
    "PENDING", "DONE", "FAILED", "EMPTY", name="extractionstatus", create_type=False,
)
_chatmessagerole = postgresql.ENUM("USER", "ASSISTANT", name="chatmessagerole", create_type=False)


def upgrade() -> None:
    _extractionstatus.create(op.get_bind(), checkfirst=True)
    _chatmessagerole.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TYPE lessonplangenerationstage ADD VALUE IF NOT EXISTS 'CHAT'")

    op.create_table(
        "curriculum_material",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("class_subject.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_status", _extractionstatus, nullable=False, server_default="PENDING"),
        sa.Column("extraction_error", sa.Text, nullable=True),
    )

    op.create_table(
        "curriculum_material_chunk",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("curriculum_material.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=False),
    )
    op.create_index(
        "ix_curriculum_material_chunk_search_vector",
        "curriculum_material_chunk", ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "lesson_plan_chat_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("lesson_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lesson_plan.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", _chatmessagerole, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lesson_plan_chat_message")
    op.drop_index("ix_curriculum_material_chunk_search_vector", table_name="curriculum_material_chunk")
    op.drop_table("curriculum_material_chunk")
    op.drop_table("curriculum_material")
    # Postgres can't drop a single enum value — downgrade leaves CHAT in
    # place (harmless, matches this project's existing precedent for
    # ADD VALUE migrations with no clean reverse).
    _chatmessagerole.drop(op.get_bind(), checkfirst=True)
    _extractionstatus.drop(op.get_bind(), checkfirst=True)
