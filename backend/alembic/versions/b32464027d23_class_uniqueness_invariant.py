"""class uniqueness invariant

Revision ID: b32464027d23
Revises: 161935b6a857
Create Date: 2026-08-16 08:10:19.558420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b32464027d23'
down_revision: Union[str, None] = '161935b6a857'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL-safe: two Basic-school classes (programme_id=NULL, stream=NULL)
    # must still collide as duplicates, which a plain UniqueConstraint would
    # not catch (SQL NULL != NULL). No existing dev data violates this
    # (checked directly before writing this migration), so no cleanup step
    # is needed here — a school hitting this for the first time via the API
    # already gets a clean 422 from create_class()'s own pre-check.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_class_school_level_year_programme_stream
        ON class (
            school_id, level, year_group,
            coalesce(programme_id, '00000000-0000-0000-0000-000000000000'::uuid),
            coalesce(stream, '')
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_class_school_level_year_programme_stream")
