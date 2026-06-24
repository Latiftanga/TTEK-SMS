"""exeat_type

Revision ID: cd0c74eba66e
Revises: fee01
Create Date: 2026-06-23 23:28:54.801786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'cd0c74eba66e'
down_revision: Union[str, None] = 'fee01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE exeattype AS ENUM ('INTERNAL', 'EXTERNAL')")
    op.add_column(
        'exeat',
        sa.Column(
            'exeat_type',
            sa.Enum('INTERNAL', 'EXTERNAL', name='exeattype', create_type=False),
            nullable=False,
            server_default='EXTERNAL',
        ),
    )


def downgrade() -> None:
    op.drop_column('exeat', 'exeat_type')
    op.execute("DROP TYPE exeattype")
