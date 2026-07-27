"""Subject teacher scoped to academic year, not term

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-07-26

SubjectTeacher previously required a separate assignment per academic_term,
mirroring how ClassTeacher is scoped by academic_year only — one subject
teacher per class+subject per year, not re-assigned every semester. A
mid-year teacher change is now just an update to the existing row.

Backfills academic_year_id from each row's current academic_term, then
collapses any rows that collide once term granularity is dropped (a school
that genuinely swapped teachers mid-year, one row per term, is a legitimate
prior case) — kept by preferring is_active=true, then the row belonging to
the highest term_number (the most recent assignment as of the migration).
academic_term_id is dropped entirely; downgrade() cannot reconstruct the
collapsed per-term history (documented, best-effort only).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subject_teacher",
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("""
        UPDATE subject_teacher st
        SET academic_year_id = at.academic_year_id
        FROM academic_term at
        WHERE st.academic_term_id = at.id
    """)
    op.execute("""
        WITH ranked AS (
            SELECT st.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY st.class_id, st.subject_id, st.academic_year_id
                       ORDER BY st.is_active DESC, at.term_number DESC
                   ) AS rn
            FROM subject_teacher st
            JOIN academic_term at ON at.id = st.academic_term_id
        )
        DELETE FROM subject_teacher WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
    """)
    op.alter_column("subject_teacher", "academic_year_id", nullable=False)
    op.create_foreign_key(
        "subject_teacher_academic_year_id_fkey", "subject_teacher", "academic_year",
        ["academic_year_id"], ["id"], ondelete="CASCADE",
    )
    op.drop_constraint("uq_subject_teacher_term", "subject_teacher", type_="unique")
    op.create_unique_constraint(
        "uq_subject_teacher_year", "subject_teacher", ["class_id", "subject_id", "academic_year_id"],
    )
    op.drop_constraint("subject_teacher_academic_term_id_fkey", "subject_teacher", type_="foreignkey")
    op.drop_column("subject_teacher", "academic_term_id")


def downgrade() -> None:
    op.add_column(
        "subject_teacher",
        sa.Column("academic_term_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Best-effort only: picks each year's first term as a placeholder — the
    # original per-term assignments collapsed by upgrade() are not recoverable.
    op.execute("""
        UPDATE subject_teacher st
        SET academic_term_id = (
            SELECT at.id FROM academic_term at
            WHERE at.academic_year_id = st.academic_year_id
            ORDER BY at.term_number ASC LIMIT 1
        )
    """)
    op.create_foreign_key(
        "subject_teacher_academic_term_id_fkey", "subject_teacher", "academic_term",
        ["academic_term_id"], ["id"], ondelete="CASCADE",
    )
    op.drop_constraint("uq_subject_teacher_year", "subject_teacher", type_="unique")
    op.create_unique_constraint(
        "uq_subject_teacher_term", "subject_teacher", ["class_id", "subject_id", "academic_term_id"],
    )
    op.drop_constraint("subject_teacher_academic_year_id_fkey", "subject_teacher", type_="foreignkey")
    op.drop_column("subject_teacher", "academic_year_id")
