"""Add staff_job_class; migrate StaffMember to job_class_id; clean StaffPromotion.

Replaces the free-text job_title + staffcategory enum with a proper FK to the
new staff_job_class reference table.  StaffPromotion loses staff_category and
non_teaching_group (those fields were never populated in production because the
migration adding them was immediately followed by this redesign).

Revision ID: t5u6v7w8x9y0
Revises:     s4t5u6v7w8x9
Create Date: 2026-06-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "t5u6v7w8x9y0"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create staff_job_class table
    op.create_table(
        "staff_job_class",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_staff_job_class_school_id", "staff_job_class", ["school_id"])
    op.create_unique_constraint(
        "uq_staff_job_class_school_code", "staff_job_class", ["school_id", "code"]
    )

    # 2. Add job_class_id to staff_member (nullable FK)
    op.add_column(
        "staff_member",
        sa.Column("job_class_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff_job_class.id", ondelete="SET NULL"),
                  nullable=True),
    )
    op.create_index("ix_staff_member_job_class_id", "staff_member", ["job_class_id"])

    # 3. Drop job_title from staff_member (added in s4t5u6v7w8x9 — never used in prod)
    op.drop_column("staff_member", "job_title")

    # 4. Drop staff_category from staff_member (was SAEnum staffcategory)
    op.drop_column("staff_member", "staff_category")

    # 5. Drop staff_category and non_teaching_group from staff_promotion
    op.drop_column("staff_promotion", "staff_category")
    op.drop_column("staff_promotion", "non_teaching_group")

    # 6. Drop the staffcategory enum type
    op.execute("DROP TYPE IF EXISTS staffcategory")


def downgrade() -> None:
    # Re-create enum
    op.execute("CREATE TYPE staffcategory AS ENUM ('TEACHING', 'NON_TEACHING')")

    # Restore staff_promotion columns
    op.add_column(
        "staff_promotion",
        sa.Column("staff_category", sa.Enum("TEACHING", "NON_TEACHING", name="staffcategory"),
                  nullable=True),
    )
    op.add_column(
        "staff_promotion",
        sa.Column("non_teaching_group", sa.String(100), nullable=True),
    )

    # Restore staff_member columns
    op.add_column(
        "staff_member",
        sa.Column("staff_category", sa.Enum("TEACHING", "NON_TEACHING", name="staffcategory"),
                  nullable=True),
    )
    op.add_column(
        "staff_member",
        sa.Column("job_title", sa.String(200), nullable=True),
    )

    # Drop job_class_id
    op.drop_index("ix_staff_member_job_class_id", "staff_member")
    op.drop_column("staff_member", "job_class_id")

    # Drop staff_job_class table
    op.drop_index("ix_staff_job_class_school_id", "staff_job_class")
    op.drop_constraint("uq_staff_job_class_school_code", "staff_job_class", type_="unique")
    op.drop_table("staff_job_class")
