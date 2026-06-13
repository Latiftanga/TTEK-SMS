"""phase5_housing_unique_house_code

Revision ID: b7f3a1c09d52
Revises: 424ee848f089
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f3a1c09d52'
down_revision: Union[str, None] = '424ee848f089'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint('uq_house_school_code', 'house', ['school_id', 'code'])


def downgrade() -> None:
    op.drop_constraint('uq_house_school_code', 'house', type_='unique')
