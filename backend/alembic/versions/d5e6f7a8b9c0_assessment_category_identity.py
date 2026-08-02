"""Assessment category identity

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-08-01

An assessment's identity is (class, subject, term, category, recorded_date),
not a teacher-typed name — "Category" (AssessmentType) is the meaningful
thing, and the date it was recorded is what disambiguates repeat instances
of the same category. name -> description (optional, supplementary detail
only); new recorded_date, server-set to today() at creation, never
client-supplied or editable afterward.

Live data backfill: description is seeded from the old name; recorded_date
is seeded from created_at::date. Same-day duplicates of the same category
(a real possibility in already-recorded data) are resolved before the new
UNIQUE constraint is added by bumping later duplicates forward a day each,
keyed by creation order — same dedup approach already used by this
codebase's subject_teacher year-collapse migration (y0z1a2b3c4d5).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessment", sa.Column("description", sa.String(200), nullable=True))
    op.execute("UPDATE assessment SET description = name")
    op.drop_column("assessment", "name")

    op.add_column("assessment", sa.Column("recorded_date", sa.Date(), nullable=True))
    op.execute("UPDATE assessment SET recorded_date = created_at::date")

    op.execute("""
        WITH ranked AS (
          SELECT id, row_number() OVER (
            PARTITION BY class_id, subject_id, academic_term_id, assessment_type_id, recorded_date
            ORDER BY created_at
          ) AS rn
          FROM assessment
        )
        UPDATE assessment a SET recorded_date = a.recorded_date + (ranked.rn - 1)::integer
        FROM ranked WHERE a.id = ranked.id AND ranked.rn > 1
    """)

    op.alter_column("assessment", "recorded_date", nullable=False)
    op.create_unique_constraint(
        "uq_assessment_category_per_day", "assessment",
        ["class_id", "subject_id", "academic_term_id", "assessment_type_id", "recorded_date"],
    )


def downgrade() -> None:
    # Best-effort/lossy: cannot reconstruct a required `name` for rows whose
    # description ended up NULL, and cannot undo the same-day dedup date
    # shifting above (same caveat as y0z1a2b3c4d5's downgrade).
    op.drop_constraint("uq_assessment_category_per_day", "assessment", type_="unique")
    op.drop_column("assessment", "recorded_date")
    op.add_column("assessment", sa.Column("name", sa.String(200), nullable=True))
    op.execute("UPDATE assessment SET name = COALESCE(description, 'Assessment')")
    op.alter_column("assessment", "name", nullable=False)
    op.drop_column("assessment", "description")
