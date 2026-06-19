"""Add ai_config table for per-school AI provider configuration

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "v7w8x9y0z1a2"
down_revision = "u6v7w8x9y0z1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE aiprovider AS ENUM ('GEMINI', 'GROQ', 'ANTHROPIC', 'OPENAI')")
    op.execute("""
        CREATE TABLE ai_config (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            school_id   UUID NOT NULL REFERENCES school(id) ON DELETE CASCADE,
            provider    aiprovider NOT NULL,
            api_key     VARCHAR(500) NOT NULL,
            model       VARCHAR(100),
            daily_limit_per_teacher INTEGER NOT NULL DEFAULT 10,
            is_active   BOOLEAN NOT NULL DEFAULT false,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_ai_config_school_provider UNIQUE (school_id, provider)
        )
    """)
    op.create_index("ix_ai_config_school_id", "ai_config", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_config_school_id", "ai_config")
    op.execute("DROP TABLE ai_config")
    op.execute("DROP TYPE aiprovider")
