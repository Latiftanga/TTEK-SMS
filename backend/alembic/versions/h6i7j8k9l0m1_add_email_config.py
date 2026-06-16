"""Add email_config and email_log tables

Revision ID: h6i7j8k9l0m1
Revises: f4c9b2e10a87
Create Date: 2026-06-16

"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h6i7j8k9l0m1"
down_revision = "f4c9b2e10a87"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE emailprovider AS ENUM ('SMTP', 'SENDGRID', 'MAILGUN', 'BREVO')")
    op.execute("CREATE TYPE emailstatus AS ENUM ('SENT', 'FAILED')")

    op.create_table(
        "email_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.Enum("SMTP", "SENDGRID", "MAILGUN", "BREVO", name="emailprovider", create_type=False), nullable=False),
        sa.Column("host", sa.String(253), nullable=True),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("username", sa.String(500), nullable=False),
        sa.Column("password", sa.String(500), nullable=True),
        sa.Column("from_name", sa.String(100), nullable=False),
        sa.Column("from_address", sa.String(200), nullable=False),
        sa.Column("use_tls", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "email_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.Enum("SMTP", "SENDGRID", "MAILGUN", "BREVO", name="emailprovider", create_type=False), nullable=False),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("status", sa.Enum("SENT", "FAILED", name="emailstatus", create_type=False), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_log")
    op.drop_table("email_config")
    op.execute("DROP TYPE emailstatus")
    op.execute("DROP TYPE emailprovider")
