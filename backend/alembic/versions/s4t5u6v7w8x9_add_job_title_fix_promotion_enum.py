"""Add job_title to staff_member; fix staff_promotion.staff_category to enum type.

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staff_member", sa.Column("job_title", sa.String(100), nullable=True))

    # staffcategory enum already exists — cast the varchar column to it.
    op.execute(
        "ALTER TABLE staff_promotion "
        "ALTER COLUMN staff_category TYPE staffcategory "
        "USING staff_category::staffcategory"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE staff_promotion "
        "ALTER COLUMN staff_category TYPE varchar(20) "
        "USING staff_category::text"
    )

    op.drop_column("staff_member", "job_title")
