"""Term results lock + behaviour audit log

Revision ID: b1c2d3e4f5a6
Revises: a8b9c0d1e2f3
Create Date: 2026-07-14

Adds AcademicTerm.results_locked (+ set_by/set_at, mirroring
block_owing_students) which freezes submit_scores/approve_scores and
behaviour record create/delete for that term. Also adds behaviour_audit_log,
mirroring score_audit_log, since StudentBehaviourRecord previously had no
audit trail at all.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1c2d3e4f5a6"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "academic_term",
        sa.Column("results_locked", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "academic_term",
        sa.Column("results_locked_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
    )
    op.add_column(
        "academic_term",
        sa.Column("results_locked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "behaviour_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("behaviour_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_behaviour_record.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("incident_type", sa.String(100), nullable=False),
        sa.Column("incident_date", sa.Date, nullable=False),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("behaviour_audit_log")

    op.drop_column("academic_term", "results_locked_at")
    op.drop_column("academic_term", "results_locked_by_id")
    op.drop_column("academic_term", "results_locked")
