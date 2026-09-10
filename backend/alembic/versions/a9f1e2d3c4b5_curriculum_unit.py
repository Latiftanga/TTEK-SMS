"""curriculum_unit table + CurriculumMaterial unit-extraction status

Revision ID: a9f1e2d3c4b5
Revises: d6e7f8a9b0c1
Create Date: 2026-08-31

New table, second independent pipeline stage from the existing page-text
extraction (extraction_status) — see services/curriculum_unit_extraction.py.
Additive only; nothing existing is touched.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a9f1e2d3c4b5"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "curriculum_unit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("curriculum_material.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("unit_label", sa.String(100), nullable=True),
        sa.Column("strand", sa.Text(), nullable=True),
        sa.Column("sub_strand", sa.Text(), nullable=True),
        sa.Column("content_standard", sa.Text(), nullable=True),
        sa.Column("indicator", sa.Text(), nullable=True),
        sa.Column("learning_objectives", sa.Text(), nullable=True),
        sa.Column("topics", sa.Text(), nullable=True),
        sa.Column("source_page_start", sa.Integer(), nullable=False),
        sa.Column("source_page_end", sa.Integer(), nullable=False),
        sa.UniqueConstraint("material_id", "sequence_number", name="uq_curriculum_unit_material_sequence"),
    )
    op.create_index("ix_curriculum_unit_school_id", "curriculum_unit", ["school_id"])
    op.create_index("ix_curriculum_unit_material_id", "curriculum_unit", ["material_id"])

    op.add_column(
        "curriculum_material",
        sa.Column("unit_extraction_status", sa.Enum(
            "PENDING", "DONE", "FAILED", "EMPTY", name="extractionstatus", create_type=False,
        ), nullable=False, server_default="PENDING"),
    )
    op.add_column("curriculum_material", sa.Column("unit_extraction_error", sa.Text(), nullable=True))
    op.alter_column("curriculum_material", "unit_extraction_status", server_default=None)


def downgrade() -> None:
    op.drop_column("curriculum_material", "unit_extraction_error")
    op.drop_column("curriculum_material", "unit_extraction_status")
    op.drop_index("ix_curriculum_unit_material_id", table_name="curriculum_unit")
    op.drop_index("ix_curriculum_unit_school_id", table_name="curriculum_unit")
    op.drop_table("curriculum_unit")
