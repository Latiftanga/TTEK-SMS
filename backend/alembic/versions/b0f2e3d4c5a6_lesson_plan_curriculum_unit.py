"""lesson_plan: curriculum_unit_id, strand/sub_strand, widen content_standard/indicator

Revision ID: b0f2e3d4c5a6
Revises: a9f1e2d3c4b5
Create Date: 2026-08-31

content_standard/indicator widen from VARCHAR(300) to TEXT — a real
extracted indicator/content-standard sentence (autofilled from a
CurriculumUnit, new in this migration) can run past what a short manual
entry needed; VARCHAR -> TEXT is lossless and non-breaking. curriculum_unit_id
mirrors curriculum_standard_id's existing SET NULL, no-cascade convention —
a second, independent optional autofill source.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b0f2e3d4c5a6"
down_revision = "a9f1e2d3c4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("lesson_plan", "content_standard", type_=sa.Text(), existing_type=sa.String(300))
    op.alter_column("lesson_plan", "indicator", type_=sa.Text(), existing_type=sa.String(300))
    op.add_column("lesson_plan", sa.Column("strand", sa.Text(), nullable=True))
    op.add_column("lesson_plan", sa.Column("sub_strand", sa.Text(), nullable=True))
    op.add_column(
        "lesson_plan",
        sa.Column("curriculum_unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("curriculum_unit.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lesson_plan", "curriculum_unit_id")
    op.drop_column("lesson_plan", "sub_strand")
    op.drop_column("lesson_plan", "strand")
    # Lossy if any existing value exceeds 300 chars — truncates on downgrade.
    op.alter_column("lesson_plan", "indicator", type_=sa.String(300), existing_type=sa.Text())
    op.alter_column("lesson_plan", "content_standard", type_=sa.String(300), existing_type=sa.Text())
