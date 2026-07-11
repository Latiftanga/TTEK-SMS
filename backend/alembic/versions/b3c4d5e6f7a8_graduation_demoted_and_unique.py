"""Add DEMOTED to graduationtype enum; unique (school, student, year) on graduation_record

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-11

"""
from alembic import op

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE graduationtype ADD VALUE IF NOT EXISTS 'DEMOTED'")
    op.create_unique_constraint(
        'uq_graduation_record_student_year', 'graduation_record',
        ['school_id', 'student_id', 'academic_year_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_graduation_record_student_year', 'graduation_record', type_='unique')
    # Postgres does not support removing enum values — DEMOTED is left in place.
