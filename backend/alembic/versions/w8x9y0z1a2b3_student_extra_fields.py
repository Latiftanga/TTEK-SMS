"""student extra fields: nhis, ghana card, boarding, orphan, disability

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-06-19
"""
from alembic import op

revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE student
            ADD COLUMN IF NOT EXISTS nhis_number       VARCHAR(50),
            ADD COLUMN IF NOT EXISTS ghana_card_number VARCHAR(50),
            ADD COLUMN IF NOT EXISTS is_boarding       BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS orphan_status     VARCHAR(20) NOT NULL DEFAULT 'NONE',
            ADD COLUMN IF NOT EXISTS disability        VARCHAR(200)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE student
            DROP COLUMN IF EXISTS nhis_number,
            DROP COLUMN IF EXISTS ghana_card_number,
            DROP COLUMN IF EXISTS is_boarding,
            DROP COLUMN IF EXISTS orphan_status,
            DROP COLUMN IF EXISTS disability
    """)
