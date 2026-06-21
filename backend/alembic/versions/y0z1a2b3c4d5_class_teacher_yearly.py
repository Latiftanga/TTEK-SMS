"""class_teacher: per-year instead of per-term

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-06-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'y0z1a2b3c4d5'
down_revision = 'x9y0z1a2b3c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('uq_class_teacher_term', 'class_teacher', type_='unique')
    op.drop_constraint('class_teacher_academic_term_id_fkey', 'class_teacher', type_='foreignkey')
    op.drop_column('class_teacher', 'academic_term_id')

    op.add_column('class_teacher',
        sa.Column('academic_year_id', UUID(as_uuid=True), nullable=False)
    )
    op.create_foreign_key(
        'class_teacher_academic_year_id_fkey',
        'class_teacher', 'academic_year',
        ['academic_year_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_unique_constraint('uq_class_teacher_year', 'class_teacher', ['class_id', 'academic_year_id'])


def downgrade() -> None:
    op.drop_constraint('uq_class_teacher_year', 'class_teacher', type_='unique')
    op.drop_constraint('class_teacher_academic_year_id_fkey', 'class_teacher', type_='foreignkey')
    op.drop_column('class_teacher', 'academic_year_id')

    op.add_column('class_teacher',
        sa.Column('academic_term_id', UUID(as_uuid=True), nullable=False)
    )
    op.create_foreign_key(
        'class_teacher_academic_term_id_fkey',
        'class_teacher', 'academic_term',
        ['academic_term_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_unique_constraint('uq_class_teacher_term', 'class_teacher', ['class_id', 'academic_term_id'])
