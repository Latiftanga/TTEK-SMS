"""Timetable slot

Revision ID: f9a0b1c2d3e4
Revises: d2e3f4a5b6c7
Create Date: 2026-08-29

Adds timetable_slot — a class's weekly timetable. day_of_week/start_time/
end_time are deliberately not stored here: they're read by joining
school_period, and the teacher by joining subject_teacher on
(class_id, subject_id, academic_year_id).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f9a0b1c2d3e4"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "timetable_slot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("academic_year.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_period.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.UniqueConstraint("class_id", "period_id", "academic_year_id", name="uq_timetable_slot_class_period_year"),
    )


def downgrade() -> None:
    op.drop_table("timetable_slot")
