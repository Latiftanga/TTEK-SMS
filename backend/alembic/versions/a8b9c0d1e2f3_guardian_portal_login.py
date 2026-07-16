"""Guardian portal login — User.guardian_id + real DB check constraints

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-07-13

Also retroactively creates ck_user_admission_id_matches_login_type and a
three-way ck_user_single_identity — both existed only in the SQLAlchemy
model's __table_args__ since the Phase 1 baseline, never actually applied to
the database (confirmed via \\d "user" against the live schema: only
uq_user_school_admission existed). No existing rows violate either rule
(verified via COUNT(*) before writing this migration), so this is safe to
apply directly rather than needing a backfill step.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a8b9c0d1e2f3"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guardian.id", ondelete="SET NULL"), nullable=True),
    )

    op.create_check_constraint(
        "ck_user_admission_id_matches_login_type",
        "user",
        "(login_type = 'ADMISSION_ID' AND admission_id IS NOT NULL)"
        " OR (login_type != 'ADMISSION_ID' AND admission_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_user_single_identity",
        "user",
        "NOT (staff_member_id IS NOT NULL AND student_id IS NOT NULL)"
        " AND NOT (staff_member_id IS NOT NULL AND guardian_id IS NOT NULL)"
        " AND NOT (student_id IS NOT NULL AND guardian_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_single_identity", "user", type_="check")
    op.drop_constraint("ck_user_admission_id_matches_login_type", "user", type_="check")
    op.drop_column("user", "guardian_id")
