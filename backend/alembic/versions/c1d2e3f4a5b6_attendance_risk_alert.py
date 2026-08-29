"""Attendance risk alert

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-08-29

Adds attendance_risk_alert — tracks the highest chronic-absenteeism tier
(WATCH/AT_RISK/SEVERE) a student has already been alerted for, per term,
so a guardian isn't re-SMS'd on every subsequent absence within the same
tier. See services/attendance_risk.py for the tier thresholds.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

_risktier = postgresql.ENUM("WATCH", "AT_RISK", "SEVERE", name="attendancerisktier", create_type=False)


def upgrade() -> None:
    _risktier.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "attendance_risk_alert",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("academic_term_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("academic_term.id"), nullable=False),
        sa.Column("tier", _risktier, nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "academic_term_id", name="uq_attendance_risk_alert"),
    )


def downgrade() -> None:
    op.drop_table("attendance_risk_alert")
    _risktier.drop(op.get_bind(), checkfirst=True)
