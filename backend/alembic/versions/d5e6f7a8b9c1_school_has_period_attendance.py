"""school.has_period_attendance

Revision ID: d5e6f7a8b9c1
Revises: c3d4e5f6a7b9
Create Date: 2026-08-29

Daily (whole-day) attendance stays the default and unconditional — this
opts a school into the ADDITIONAL per-period marking layer.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c1"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "school",
        sa.Column("has_period_attendance", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("school", "has_period_attendance")
