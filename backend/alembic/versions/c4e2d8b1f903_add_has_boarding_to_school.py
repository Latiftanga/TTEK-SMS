"""add_has_boarding_to_school

Revision ID: c4e2d8b1f903
Revises: b7f3a1c09d52
Create Date: 2026-06-13 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e2d8b1f903'
down_revision: Union[str, None] = 'b7f3a1c09d52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'school',
        sa.Column('has_boarding', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('school', 'has_boarding')
