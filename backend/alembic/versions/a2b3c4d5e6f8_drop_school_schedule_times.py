"""Drop dead school_schedule start_time/end_time

Revision ID: a2b3c4d5e6f8
Revises: f9a0b1c2d3e4
Create Date: 2026-08-29

school_schedule.start_time/end_time were stored and displayed on the
Attendance Schedule page but never consulted by any code path —
generate_calendar() only ever reads is_school_day. SchoolPeriod is now the
sole source of a day's time structure. Confirmed via full-codebase grep
before dropping.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f8"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("school_schedule", "start_time")
    op.drop_column("school_schedule", "end_time")


def downgrade() -> None:
    # Lossy — the original time values are not recoverable, matching this
    # codebase's existing convention for similar cleanup migrations.
    op.add_column("school_schedule", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("school_schedule", sa.Column("end_time", sa.Time(), nullable=True))
