"""ai_config: at most one active row per scope

Revision ID: d6e7f8a9b0c1
Revises: c4d8e2f6a9b1
Create Date: 2026-08-30

Closes a race code-review found in activate_ai_provider() (services/
ai_config.py): deactivate-then-activate is two non-atomic statements, so two
concurrent "activate" calls for the same scope (a school, or — since
school_id is nullable since b3c9d7a1e5f2 — the platform-default row) can
both leave a row is_active=True. resolve_driver_for_generation()'s plain
db.scalar() would then silently return whichever row Postgres orders first,
making the resolved provider unpredictable. This is a DB-level backstop,
same role as 161935b6a857's academic year/term "one current" indexes;
activate_ai_provider() itself is unaffected — the app-level deactivate-then-
activate already prevents this in the non-concurrent case.

NULL-safe (coalesce), matching b32464027d23's precedent — two platform-
default rows (school_id=NULL) must collide as duplicates, which a plain
partial unique index would not catch (SQL NULL != NULL). Zero existing rows
violate this today (checked directly against the live dev DB before writing
this migration: `SELECT coalesce(school_id::text,'NULL'), count(*) FROM
ai_config WHERE is_active GROUP BY 1 HAVING count(*) > 1;` — zero rows), so
no cleanup step is included.
"""
from __future__ import annotations

from alembic import op

revision = "d6e7f8a9b0c1"
down_revision = "c4d8e2f6a9b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ai_config_one_active_per_scope
        ON ai_config (coalesce(school_id, '00000000-0000-0000-0000-000000000000'::uuid))
        WHERE is_active
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ai_config_one_active_per_scope")
