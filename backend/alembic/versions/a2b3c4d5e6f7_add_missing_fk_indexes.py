"""Add missing FK indexes on fees and assessments tables

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-06-24

"""
from alembic import op

revision = 'a2b3c4d5e6f7'
down_revision = 'cd0c74eba66e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # student_fee_record
    op.create_index('ix_student_fee_record_academic_term_id', 'student_fee_record', ['academic_term_id'])
    op.create_index('ix_student_fee_record_fee_structure_id', 'student_fee_record', ['fee_structure_id'])

    # fee_payment
    op.create_index('ix_fee_payment_academic_term_id', 'fee_payment', ['academic_term_id'])

    # fee_discount
    op.create_index('ix_fee_discount_academic_term_id', 'fee_discount', ['academic_term_id'])
    op.create_index('ix_fee_discount_fee_record_id', 'fee_discount', ['fee_record_id'])

    # fee_instalment_plan
    op.create_index('ix_fee_instalment_plan_fee_record_id', 'fee_instalment_plan', ['fee_record_id'])

    # assessment
    op.create_index('ix_assessment_subject_id', 'assessment', ['subject_id'])
    op.create_index('ix_assessment_assessment_type_id', 'assessment', ['assessment_type_id'])
    op.create_index('ix_assessment_academic_term_id', 'assessment', ['academic_term_id'])


def downgrade() -> None:
    op.drop_index('ix_assessment_academic_term_id', 'assessment')
    op.drop_index('ix_assessment_assessment_type_id', 'assessment')
    op.drop_index('ix_assessment_subject_id', 'assessment')
    op.drop_index('ix_fee_instalment_plan_fee_record_id', 'fee_instalment_plan')
    op.drop_index('ix_fee_discount_fee_record_id', 'fee_discount')
    op.drop_index('ix_fee_discount_academic_term_id', 'fee_discount')
    op.drop_index('ix_fee_payment_academic_term_id', 'fee_payment')
    op.drop_index('ix_student_fee_record_fee_structure_id', 'student_fee_record')
    op.drop_index('ix_student_fee_record_academic_term_id', 'student_fee_record')
