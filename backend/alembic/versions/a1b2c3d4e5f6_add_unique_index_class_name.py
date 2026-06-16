"""add unique index on class name (school+year+level+year_group+programme+stream)

Revision ID: a1b2c3d4e5f6
Revises: f4c9b2e10a87
Create Date: 2026-06-15

Uses a functional index with COALESCE so that NULL values in programme_id and
stream are treated as equal (PostgreSQL otherwise considers NULL != NULL, which
would allow unlimited duplicate classes with null stream/programme).
"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f4c9b2e10a87'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove any duplicates introduced before this constraint existed.
    # Keeps the earliest-created row for each logical class name.
    op.execute("""
        DELETE FROM "class"
        WHERE id NOT IN (
            SELECT DISTINCT ON (
                school_id, academic_year_id, level, year_group,
                COALESCE(programme_id::text, ''),
                COALESCE(stream, '')
            ) id
            FROM "class"
            ORDER BY
                school_id, academic_year_id, level, year_group,
                COALESCE(programme_id::text, ''), COALESCE(stream, ''),
                created_at ASC
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_class_name ON "class" (
            school_id,
            academic_year_id,
            level,
            year_group,
            COALESCE(programme_id::text, ''),
            COALESCE(stream, '')
        )
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_class_name')
