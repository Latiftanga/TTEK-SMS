"""fee_structure: add applies_to_class_id, boarding_only; add EXEMPTION discount type

Revision ID: fee01
Revises: z1a2b3c4d5e6
Create Date: 2026-06-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'fee01'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('fee_structure',
        sa.Column('applies_to_class_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_fee_structure_class', 'fee_structure', 'class',
        ['applies_to_class_id'], ['id'], ondelete='SET NULL')

    op.add_column('fee_structure',
        sa.Column('boarding_only', sa.Boolean(), server_default='false', nullable=False))

    op.execute("ALTER TYPE discounttype ADD VALUE IF NOT EXISTS 'EXEMPTION'")


def downgrade() -> None:
    op.drop_constraint('fk_fee_structure_class', 'fee_structure', type_='foreignkey')
    op.drop_column('fee_structure', 'applies_to_class_id')
    op.drop_column('fee_structure', 'boarding_only')
    # PostgreSQL does not support removing enum values; leave EXEMPTION in place
