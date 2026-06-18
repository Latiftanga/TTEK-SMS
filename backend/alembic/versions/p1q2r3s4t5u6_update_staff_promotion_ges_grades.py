"""Replace staff_promotion FK columns with GES grade string columns

Revision ID: p1q2r3s4t5u6
Revises: h6i7j8k9l0m1
Create Date: 2026-06-16

"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p1q2r3s4t5u6"
down_revision = "h6i7j8k9l0m1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("staff_promotion")
    op.create_table(
        "staff_promotion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("staff_member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("staff_category", sa.String(20), nullable=False),
        sa.Column("non_teaching_group", sa.String(100), nullable=True),
        sa.Column("from_grade", sa.String(200), nullable=True),
        sa.Column("to_grade", sa.String(200), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("staff_promotion")
    op.create_table(
        "staff_promotion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("staff_member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_position_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_position.id"), nullable=True),
        sa.Column("to_position_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_position.id"), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
