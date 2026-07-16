"""Assessment audit log

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-16

Adds assessment_audit_log, mirroring behaviour_audit_log/score_audit_log.
update_assessment previously validated a locked-term override_reason but
discarded it — every field edit is now written here with an old/new value
snapshot, reason populated only for locked-term overrides.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessment.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("old_values", postgresql.JSONB, nullable=False),
        sa.Column("new_values", postgresql.JSONB, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assessment_audit_log")
