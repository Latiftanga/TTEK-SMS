"""Add StaffCategory, StaffRank, SchoolOwnership; replace StaffJobClass

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. School ownership
    op.execute("CREATE TYPE schoolownership AS ENUM ('PUBLIC', 'PRIVATE')")
    op.add_column("school", sa.Column(
        "ownership",
        postgresql.ENUM("PUBLIC", "PRIVATE", name="schoolownership", create_type=False),
        nullable=False,
        server_default="PUBLIC",
    ))

    # 2. StaffType enum
    op.execute("CREATE TYPE stafftype AS ENUM ('TEACHING', 'NON_TEACHING')")

    # 3. staff_category table
    op.create_table(
        "staff_category",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("staff_type",
                  postgresql.ENUM("TEACHING", "NON_TEACHING", name="stafftype", create_type=False),
                  nullable=True),
        sa.Column("is_template", sa.Boolean, nullable=False, default=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.UniqueConstraint("school_id", "code", name="uq_staff_category_school_code"),
    )
    op.create_index("ix_staff_category_school_id", "staff_category", ["school_id"])

    # 4. staff_rank table
    op.create_table(
        "staff_rank",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff_category.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("is_template", sa.Boolean, nullable=False, default=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.UniqueConstraint("school_id", "category_id", "title", name="uq_staff_rank_school_cat_title"),
    )
    op.create_index("ix_staff_rank_school_id", "staff_rank", ["school_id"])
    op.create_index("ix_staff_rank_category_id", "staff_rank", ["category_id"])

    # 5. staff_member: swap job_class_id → category_id
    op.add_column("staff_member", sa.Column(
        "category_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("staff_category.id", ondelete="SET NULL"), nullable=True,
    ))
    op.create_index("ix_staff_member_category_id", "staff_member", ["category_id"])
    op.drop_index("ix_staff_member_job_class_id", table_name="staff_member", if_exists=True)
    op.drop_column("staff_member", "job_class_id")

    # 6. staff_promotion: replace free-text grade fields with FK references
    op.add_column("staff_promotion", sa.Column(
        "from_rank_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("staff_rank.id", ondelete="SET NULL"), nullable=True,
    ))
    op.add_column("staff_promotion", sa.Column(
        "to_rank_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("staff_rank.id", ondelete="SET NULL"), nullable=True,
    ))
    op.drop_column("staff_promotion", "from_grade")
    op.drop_column("staff_promotion", "to_grade")

    # 7. Drop the old staff_job_class table
    op.drop_table("staff_job_class")
    op.execute("DROP TYPE IF EXISTS staffcategory")  # old enum from prior migration if it exists


def downgrade() -> None:
    # Recreate staff_job_class
    op.create_table(
        "staff_job_class",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("school.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("is_template", sa.Boolean, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("school_id", "code", name="uq_staff_job_class_school_code"),
    )

    op.add_column("staff_promotion", sa.Column("from_grade", sa.String(200), nullable=True))
    op.add_column("staff_promotion", sa.Column("to_grade", sa.String(200), nullable=True))
    op.drop_column("staff_promotion", "from_rank_id")
    op.drop_column("staff_promotion", "to_rank_id")

    op.drop_index("ix_staff_member_category_id", table_name="staff_member")
    op.drop_column("staff_member", "category_id")
    op.add_column("staff_member", sa.Column(
        "job_class_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("staff_job_class.id", ondelete="SET NULL"), nullable=True,
    ))

    op.drop_table("staff_rank")
    op.drop_table("staff_category")
    op.execute("DROP TYPE IF EXISTS stafftype")
    op.drop_column("school", "ownership")
    op.execute("DROP TYPE IF EXISTS schoolownership")
