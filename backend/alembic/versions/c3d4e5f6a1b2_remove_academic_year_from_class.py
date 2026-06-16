"""Remove academic_year_id from class — classes are permanent, enrollment carries the year

Revision ID: c3d4e5f6a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16

Classes are permanent entities (e.g. "Basic 5A", "SHS 1 Business"). Students are
enrolled into a class for a specific year/term via StudentEnrollment/TermEnrollment.
Recreating a Class row each year was architecturally wrong — this migration removes
academic_year_id from the class table and rebuilds the uniqueness constraint without it.
"""
from alembic import op

revision = 'c3d4e5f6a1b2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old index (included academic_year_id)
    op.execute('DROP INDEX IF EXISTS uq_class_name')
    # Drop the column — CASCADE removes the FK constraint automatically
    op.execute('ALTER TABLE "class" DROP COLUMN IF EXISTS academic_year_id CASCADE')
    # New uniqueness: a school cannot have two classes with the same name
    op.execute("""
        CREATE UNIQUE INDEX uq_class_name ON "class" (
            school_id,
            level,
            year_group,
            COALESCE(programme_id::text, ''),
            COALESCE(stream, '')
        )
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_class_name')
    op.execute("""
        ALTER TABLE "class"
        ADD COLUMN academic_year_id UUID REFERENCES academic_year(id) ON DELETE CASCADE
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
