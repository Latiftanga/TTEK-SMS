"""Calendar override audit log

Revision ID: a1b2c3d4e5f6
Revises: 355c4338994d
Create Date: 2026-08-28

Adds calendar_override_log. override_calendar_day() previously flipped
SchoolCalendar.day_type with no audit trail at all (unlike attendance
marking's own AttendanceAuditLog for locked-term overrides) and no
restriction on which transitions were allowed — an admin could flip a day
between any of the six DayType values freely, repeatedly, all silently
unrecorded. One row is now written per override, naming who changed it,
from what, to what, and why (notes).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8c9d0e1f2a3"
down_revision = "355c4338994d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_override_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("calendar_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_calendar.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("old_day_type", postgresql.ENUM("SCHOOL_DAY", "PUBLIC_HOLIDAY", "SCHOOL_HOLIDAY", "HALF_DAY", "WEEKEND", "EXAM_DAY", name="daytype", create_type=False), nullable=False),
        sa.Column("new_day_type", postgresql.ENUM("SCHOOL_DAY", "PUBLIC_HOLIDAY", "SCHOOL_HOLIDAY", "HALF_DAY", "WEEKEND", "EXAM_DAY", name="daytype", create_type=False), nullable=False),
        sa.Column("notes", sa.String(300), nullable=True),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("calendar_override_log")
