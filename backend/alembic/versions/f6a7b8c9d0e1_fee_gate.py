"""Fee gate — block_owing_students on academic_term, waiver fields on term_enrollment

Revision ID: f6a7b8c9d0e1
Revises: b3c4d5e6f7a8
Create Date: 2026-07-12

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "academic_term",
        sa.Column("block_owing_students", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "academic_term",
        sa.Column("block_owing_students_set_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
    )
    op.add_column(
        "academic_term",
        sa.Column("block_owing_students_set_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "term_enrollment",
        sa.Column("fee_waived", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "term_enrollment",
        sa.Column("fee_waived_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
    )
    op.add_column(
        "term_enrollment",
        sa.Column("fee_waiver_reason", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("term_enrollment", "fee_waiver_reason")
    op.drop_column("term_enrollment", "fee_waived_by_id")
    op.drop_column("term_enrollment", "fee_waived")

    op.drop_column("academic_term", "block_owing_students_set_at")
    op.drop_column("academic_term", "block_owing_students_set_by")
    op.drop_column("academic_term", "block_owing_students")
