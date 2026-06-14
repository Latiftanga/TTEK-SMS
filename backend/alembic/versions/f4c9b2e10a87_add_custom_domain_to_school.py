"""add custom_domain to school

Revision ID: f4c9b2e10a87
Revises: a3f9c1e87b20
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "f4c9b2e10a87"
down_revision = "a3f9c1e87b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "school",
        sa.Column("custom_domain", sa.String(253), nullable=True),
    )
    op.create_unique_constraint("uq_school_custom_domain", "school", ["custom_domain"])
    op.create_index("ix_school_custom_domain", "school", ["custom_domain"])


def downgrade() -> None:
    op.drop_index("ix_school_custom_domain", table_name="school")
    op.drop_constraint("uq_school_custom_domain", "school", type_="unique")
    op.drop_column("school", "custom_domain")
