"""Assessment type unique per school

Revision ID: e7f8a9b0c1d2
Revises: f8a9b0c1d2e3
Create Date: 2026-08-11

create_assessment_type()/update_assessment_type() have always rejected a
duplicate code or name with a clean 409 — but only at the application layer.
Nothing at the database level stopped two concurrent requests from both
passing that check before either commits, landing two AssessmentType rows
with the same code/name for one school. Live data checked clean (no existing
duplicates), so this is purely additive — no backfill needed.
"""
from __future__ import annotations

from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_assessment_type_school_code", "assessment_type", ["school_id", "code"],
    )
    op.create_unique_constraint(
        "uq_assessment_type_school_name", "assessment_type", ["school_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_assessment_type_school_name", "assessment_type", type_="unique")
    op.drop_constraint("uq_assessment_type_school_code", "assessment_type", type_="unique")
