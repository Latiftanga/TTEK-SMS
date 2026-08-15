"""academic year/term integrity: at-most-one-current + date-order constraints

Revision ID: 161935b6a857
Revises: c4d5e6f7a8b9
Create Date: 2026-08-15

Closes a real gap: nothing at the DB layer ever prevented more than one
AcademicYear or AcademicTerm from being is_current=True for the same
school, and set_current_term (services/academic_year.py) could silently
mark a term current without its parent year also being current — a
one-click path (confirmed, not theoretical) to the exact "current year
has no current term, a different year's term is marked current instead"
drift this repo's own CLAUDE.md documented but never root-caused (12bl,
12bn). The service-layer fix (same session) makes set_current_year/
set_current_term cascade correctly; these two partial unique indexes are
what make that invariant actually hold under concurrent requests too,
not just in the common case.

Verified against the live dev DB before writing this migration: zero
rows currently violate end_date > start_date on either table, and zero
schools currently have more than one is_current=True row on either
table — this applies cleanly today. That is NOT a guarantee for every
environment; run the two SELECTs below against any other database
before applying this migration there:

    SELECT school_id, count(*) FROM academic_year  WHERE is_current GROUP BY school_id HAVING count(*) > 1;
    SELECT school_id, count(*) FROM academic_term  WHERE is_current GROUP BY school_id HAVING count(*) > 1;
    SELECT id FROM academic_year WHERE end_date <= start_date;
    SELECT id FROM academic_term WHERE end_date <= start_date;

Raw op.execute (not op.create_index) for the partial indexes, matching
this repo's own precedent in a1b2c3d4e5f6_add_unique_index_class_name.py
— a WHERE clause doesn't express cleanly through op.create_index.
"""
from alembic import op

revision = '161935b6a857'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'CREATE UNIQUE INDEX uq_academic_year_one_current_per_school '
        'ON academic_year (school_id) WHERE is_current'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_academic_term_one_current_per_school '
        'ON academic_term (school_id) WHERE is_current'
    )
    op.create_check_constraint(
        "ck_academic_year_date_order", "academic_year", "end_date > start_date",
    )
    op.create_check_constraint(
        "ck_academic_term_date_order", "academic_term", "end_date > start_date",
    )


def downgrade() -> None:
    op.drop_constraint("ck_academic_term_date_order", "academic_term", type_="check")
    op.drop_constraint("ck_academic_year_date_order", "academic_year", type_="check")
    op.execute("DROP INDEX IF EXISTS uq_academic_term_one_current_per_school")
    op.execute("DROP INDEX IF EXISTS uq_academic_year_one_current_per_school")
