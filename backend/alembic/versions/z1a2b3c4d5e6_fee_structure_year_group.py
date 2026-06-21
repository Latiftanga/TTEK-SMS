"""fee_structure: replace applies_to_level with applies_to_year_group

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-06-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'z1a2b3c4d5e6'
down_revision = 'y0z1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('fee_structure', 'applies_to_level')
    op.add_column('fee_structure', sa.Column('applies_to_year_group', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('fee_structure', 'applies_to_year_group')
    op.add_column('fee_structure', sa.Column('applies_to_level', sa.String(length=20), nullable=True))
