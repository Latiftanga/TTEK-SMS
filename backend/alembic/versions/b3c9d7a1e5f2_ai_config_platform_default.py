"""AiConfig platform-default row (nullable school_id)

Revision ID: b3c9d7a1e5f2
Revises: f1a2b3c4d5e6
Create Date: 2026-08-30

Drops the NOT NULL constraint on ai_config.school_id — mirrors
SubjectCatalogue's existing nullable-school_id convention exactly:
school_id=NULL becomes the single Tagnatek-configured platform-default row
every school falls back to when it has none of its own. Every existing
per-school row keeps its school_id populated and is completely unaffected.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b3c9d7a1e5f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ai_config", "school_id", nullable=True)


def downgrade() -> None:
    # Lossy if a platform-default row (school_id NULL) exists — delete it
    # first, since there's no school_id to backfill it with.
    op.execute("DELETE FROM ai_config WHERE school_id IS NULL")
    op.alter_column("ai_config", "school_id", nullable=False)
