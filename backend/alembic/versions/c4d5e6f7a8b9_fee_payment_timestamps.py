"""Fee payment/instalment plan gain created_at/updated_at

Revision ID: c4d5e6f7a8b9
Revises: b7c8d9e0f1a2
Create Date: 2026-08-12

fee_payment had no system timestamp at all -- payment_date is a
self-reported, unbounded, client-controlled date, so there was no way to
tell when a payment was actually entered versus what date it claims to be
for. Every other financial audit column in this module (fee_discount, ...)
already had this via TimestampMixin; fee_payment and fee_instalment_plan
didn't. server_default=now() backfills existing rows to "now" (the exact
system-entry time is unrecoverable for rows that predate this migration --
acceptable, this closes the gap going forward).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("fee_payment", "fee_instalment_plan"):
        op.add_column(table, sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False,
        ))
        op.add_column(table, sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False,
        ))


def downgrade() -> None:
    for table in ("fee_payment", "fee_instalment_plan"):
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
