"""Attendance audit log

Revision ID: 35eba42e429d
Revises: d4e8f2a91c37
Create Date: 2026-08-17

Adds attendance_audit_log, mirroring behaviour_audit_log/assessment_audit_log.
mark_attendance() previously validated a locked-term override_reason but
discarded it — one row is now written per affected student whenever a
submission overrides a locked term, naming who did it and why.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "35eba42e429d"
down_revision = "d4e8f2a91c37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("attendance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attendance_record.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("class.id"), nullable=False),
        sa.Column("status", postgresql.ENUM("PRESENT", "ABSENT", "LATE", "EXCUSED", name="attendancestatus", create_type=False), nullable=False),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("attendance_audit_log")
