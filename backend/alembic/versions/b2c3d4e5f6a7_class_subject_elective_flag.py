"""ClassSubject elective flag

Revision ID: b2c3d4e5f6a7
Revises: f7a8b9c0d1e2
Create Date: 2026-07-30

Adds ClassSubject.is_elective, so a class's curriculum can distinguish "every
student takes this" (the default) from a genuine per-student elective split.
Lets bulk_register_core_subjects() safely bulk-seed SubjectRegistration for
every non-elective subject at once without touching electives, which must
stay a deliberate per-student choice. Simple additive column — every
existing row correctly defaults to "not an elective."
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "class_subject",
        sa.Column("is_elective", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("class_subject", "is_elective")
