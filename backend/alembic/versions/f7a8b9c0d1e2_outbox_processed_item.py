"""Outbox processed item — idempotency ledger for /sync/outbox

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-07-29

Adds outbox_processed_item, keyed by (school_id, user_id, client_op_id).
A retried or duplicated submission of the same client_op_id returns the
recorded outcome instead of re-running score-apply logic, so a network
retry can't double-write a ScoreAuditLog entry or reopen a conflict.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_processed_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("client_op_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("conflict_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offline_sync_conflict.id", ondelete="SET NULL"), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_outbox_processed_item", "outbox_processed_item", ["school_id", "user_id", "client_op_id"],
    )


def downgrade() -> None:
    op.drop_table("outbox_processed_item")
