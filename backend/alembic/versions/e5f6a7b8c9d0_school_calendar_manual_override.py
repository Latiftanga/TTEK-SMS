"""SchoolCalendar manual override flag

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-27

Adds SchoolCalendar.is_manual_override, set by override_calendar_day() and
checked by generate_calendar(force=True) so a force-regeneration no longer
silently overwrites a day a staff member deliberately hand-corrected.
Simple additive column — every existing row correctly defaults to
"not manually overridden".
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "school_calendar",
        sa.Column("is_manual_override", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("school_calendar", "is_manual_override")
