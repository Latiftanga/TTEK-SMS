"""SubjectRegistrationAuditLog

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-30

register_subjects()/delete_subject_registration() already called
check_term_lock_override() but discarded the returned reason, and no audit
table existed for subject-registration changes at all — the same gap
already found and fixed for scores (ScoreAuditLog), assessments
(AssessmentAuditLog), and behaviour records (BehaviourAuditLog). Adds the
matching audit table for subject registration create/delete.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subject_registration_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("registration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject_registration.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("term_enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("term_enrollment.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject.id"), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("registration_type", sa.String(20), nullable=False),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("subject_registration_audit_log")
