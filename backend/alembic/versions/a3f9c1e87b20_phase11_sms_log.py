"""phase11: sms_log table for SMS audit trail

Revision ID: a3f9c1e87b20
Revises: e5f0a2d91c74
Create Date: 2026-06-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3f9c1e87b20"
down_revision = "e5f0a2d91c74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE smsstatus AS ENUM ('SENT', 'FAILED')")
    op.create_table(
        "sms_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", postgresql.ENUM(
            "AFRICAS_TALKING", "HUBTEL", "ARKESEL", "WIGAL", "TWILIO",
            name="smsprovider", create_type=False,
        ), nullable=False),
        sa.Column("recipient", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", postgresql.ENUM(
            "SENT", "FAILED", name="smsstatus", create_type=False,
        ), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sms_log_school_id", "sms_log", ["school_id"])
    op.create_index("ix_sms_log_sent_at", "sms_log", ["sent_at"])


def downgrade() -> None:
    op.drop_table("sms_log")
    op.execute("DROP TYPE smsstatus")
