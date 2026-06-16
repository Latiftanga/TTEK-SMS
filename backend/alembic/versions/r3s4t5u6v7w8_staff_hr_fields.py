"""Add HR fields to staff_member: staff_category, employment_type, marital_status, ssnit_number, address.

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r3s4t5u6v7w8"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None

_staffcategory  = postgresql.ENUM("TEACHING", "NON_TEACHING", name="staffcategory",  create_type=False)
_employmenttype = postgresql.ENUM("PERMANENT", "CONTRACT", "NATIONAL_SERVICE", "INTERN", name="employmenttype", create_type=False)
_maritalstatus  = postgresql.ENUM("SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "SEPARATED", name="maritalstatus", create_type=False)


def upgrade() -> None:
    _staffcategory.create(op.get_bind(),  checkfirst=True)
    _employmenttype.create(op.get_bind(), checkfirst=True)
    _maritalstatus.create(op.get_bind(),  checkfirst=True)

    op.add_column("staff_member", sa.Column("staff_category",  _staffcategory,  nullable=True))
    op.add_column("staff_member", sa.Column("employment_type", _employmenttype, nullable=True))
    op.add_column("staff_member", sa.Column("marital_status",  _maritalstatus,  nullable=True))
    op.add_column("staff_member", sa.Column("ssnit_number", sa.String(20),  nullable=True))
    op.add_column("staff_member", sa.Column("address",      sa.Text(),       nullable=True))


def downgrade() -> None:
    op.drop_column("staff_member", "address")
    op.drop_column("staff_member", "ssnit_number")
    op.drop_column("staff_member", "marital_status")
    op.drop_column("staff_member", "employment_type")
    op.drop_column("staff_member", "staff_category")

    _maritalstatus.drop(op.get_bind(),  checkfirst=True)
    _employmenttype.drop(op.get_bind(), checkfirst=True)
    _staffcategory.drop(op.get_bind(),  checkfirst=True)
