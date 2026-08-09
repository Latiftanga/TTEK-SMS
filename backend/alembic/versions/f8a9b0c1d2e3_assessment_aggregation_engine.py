"""Assessment aggregation engine — category/allow_multiple_entries/
aggregation_strategy on assessment_type

Revision ID: f8a9b0c1d2e3
Revises: e6f7a8b9c0d1
Create Date: 2026-08-09

AssessmentType gains 3 new columns (category, allow_multiple_entries,
aggregation_strategy — see services/aggregation.py) so a school can configure
per-type behavior instead of every type always being summed (sum_normalize)
and always included in term totals.

BACKWARD COMPATIBILITY — the server_default on each new column backfills
every existing row to category=FORMATIVE, allow_multiple_entries=true,
aggregation_strategy=SUM_NORMALIZE. This is deliberately NOT the "neutral"
default the engine uses for brand-new types going forward
(aggregation_strategy=AVERAGE) — sum_normalize is what
_compute_weighted_scores() has always unconditionally done, so this backfill
is behavior-preserving: no existing school's computed report-card totals
change when this migration runs. category=FORMATIVE vs SUMMATIVE makes no
computed difference for existing (non-diagnostic) data either way — schools
can reclassify individual types afterward with zero grade impact.

A once-a-year exam concept (a nullable Assessment.academic_year_id alongside
academic_term_id) was drafted alongside this migration but removed before
ever being committed — this system doesn't record year-end/terminal exam
results at all, so Assessment.academic_term_id stays NOT NULL as it always
was, with no second id to XOR against.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f8a9b0c1d2e3"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

_ASSESSMENT_CATEGORY = postgresql.ENUM(
    "DIAGNOSTIC", "FORMATIVE", "SUMMATIVE", name="assessmentcategory",
)
_AGGREGATION_STRATEGY = postgresql.ENUM(
    "NONE", "BEST_OF", "AVERAGE", "SUM_NORMALIZE", name="aggregationstrategy",
)


def upgrade() -> None:
    bind = op.get_bind()
    _ASSESSMENT_CATEGORY.create(bind, checkfirst=True)
    _AGGREGATION_STRATEGY.create(bind, checkfirst=True)

    op.add_column(
        "assessment_type",
        sa.Column(
            "category", _ASSESSMENT_CATEGORY, nullable=False,
            server_default="FORMATIVE",
        ),
    )
    op.add_column(
        "assessment_type",
        sa.Column(
            "allow_multiple_entries", sa.Boolean, nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "assessment_type",
        sa.Column(
            "aggregation_strategy", _AGGREGATION_STRATEGY, nullable=False,
            server_default="SUM_NORMALIZE",
        ),
    )


def downgrade() -> None:
    op.drop_column("assessment_type", "aggregation_strategy")
    op.drop_column("assessment_type", "allow_multiple_entries")
    op.drop_column("assessment_type", "category")

    bind = op.get_bind()
    _AGGREGATION_STRATEGY.drop(bind, checkfirst=True)
    _ASSESSMENT_CATEGORY.drop(bind, checkfirst=True)
