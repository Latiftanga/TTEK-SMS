"""school_period name/start_time/end_time unique per day

Revision ID: c3d4e5f6a7b9
Revises: a2b3c4d5e6f8
Create Date: 2026-08-29

Within the same school+day, a period's name/start_time/end_time must each be
unique (not just period_number) — prevents two periods sharing a label or a
start/end clock time on the same day. Scoped per day_of_week, not
school-wide, since the same name/start/end repeating on a different day is
normal (e.g. an identical Mon/Tue bell schedule via copy_periods_to_days).
"""
from __future__ import annotations

from alembic import op

revision = "c3d4e5f6a7b9"
down_revision = "a2b3c4d5e6f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_school_period_name", "school_period", ["school_id", "day_of_week", "name"]
    )
    op.create_unique_constraint(
        "uq_school_period_start", "school_period", ["school_id", "day_of_week", "start_time"]
    )
    op.create_unique_constraint(
        "uq_school_period_end", "school_period", ["school_id", "day_of_week", "end_time"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_school_period_end", "school_period", type_="unique")
    op.drop_constraint("uq_school_period_start", "school_period", type_="unique")
    op.drop_constraint("uq_school_period_name", "school_period", type_="unique")
