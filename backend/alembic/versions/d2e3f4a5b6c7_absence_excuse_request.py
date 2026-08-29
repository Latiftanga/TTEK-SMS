"""Absence excuse request

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-29

Adds absence_excuse_request — a guardian/student self-service absence
excuse workflow. See models/attendance_excuse.py for the full design note.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

_excusestatus = postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="excusestatus", create_type=False)


def upgrade() -> None:
    _excusestatus.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "absence_excuse_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guardian.id"), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", _excusestatus, nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("end_date >= start_date", name="ck_excuse_request_date_order"),
    )


def downgrade() -> None:
    op.drop_table("absence_excuse_request")
    _excusestatus.drop(op.get_bind(), checkfirst=True)
