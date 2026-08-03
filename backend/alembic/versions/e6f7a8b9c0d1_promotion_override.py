"""Promotion override — override_reason and source_class_id on graduation_record

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-03

process_bulk_promotion() now validates that a promotion's target class actually
continues the student's current programme/stream/level track (see
services/class_progression.py) — a programme or stream mismatch is blocked
unless the caller supplies an override_reason. Both columns stay NULL for
graduation/withdrawal/transfer rows (GraduationRecord is shared with those
outcomes via services/graduation.py) and for every ordinary promotion that
matched cleanly. source_class_id is SET NULL (not CASCADE) so the outcome
record survives a class being deleted later, matching the audit-log
convention (assessment_audit_log, subject_registration_audit_log, ...).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "graduation_record",
        sa.Column("override_reason", sa.Text, nullable=True),
    )
    op.add_column(
        "graduation_record",
        sa.Column(
            "source_class_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("class.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.create_index(
        "ix_graduation_record_source_class_id", "graduation_record", ["source_class_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_graduation_record_source_class_id", table_name="graduation_record")
    op.drop_column("graduation_record", "source_class_id")
    op.drop_column("graduation_record", "override_reason")
