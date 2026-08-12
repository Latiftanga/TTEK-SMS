"""Score audit log survives assessment/score deletion

Revision ID: b7c8d9e0f1a2
Revises: e7f8a9b0c1d2
Create Date: 2026-08-12

score_audit_log.score_id was ON DELETE CASCADE through score -> assessment,
so deleting an assessment silently erased every ScoreAuditLog row for its
scores -- the exact "who changed what, when, why" trail the table exists to
preserve. AssessmentAuditLog/BehaviourAuditLog both already use SET NULL for
this reason; score_audit_log was the one left on CASCADE. Purely additive:
column becomes nullable, FK recreated as SET NULL, no data changes.
"""
from __future__ import annotations

from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("score_audit_log", "score_id", nullable=True)
    op.drop_constraint("score_audit_log_score_id_fkey", "score_audit_log", type_="foreignkey")
    op.create_foreign_key(
        "score_audit_log_score_id_fkey",
        "score_audit_log",
        "score",
        ["score_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("score_audit_log_score_id_fkey", "score_audit_log", type_="foreignkey")
    op.create_foreign_key(
        "score_audit_log_score_id_fkey",
        "score_audit_log",
        "score",
        ["score_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("score_audit_log", "score_id", nullable=False)
