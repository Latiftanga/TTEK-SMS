"""Separate class membership from term attendance: add student_class_assignment, drop class_id from term_enrollment.

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'x9y0z1a2b3c4'
down_revision = 'w8x9y0z1a2b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'student_class_assignment',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('academic_year_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['school.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['class.id']),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_year.id']),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'academic_year_id', name='uq_student_class_year'),
    )
    op.create_index('ix_student_class_assignment_student_id', 'student_class_assignment', ['student_id'])
    op.create_index('ix_student_class_assignment_class_id', 'student_class_assignment', ['class_id'])

    # Migrate existing class associations from term_enrollment into student_class_assignment.
    # For students with multiple term enrollments in the same academic year, use the most recent one.
    op.execute("""
        INSERT INTO student_class_assignment
            (id, school_id, student_id, class_id, academic_year_id, assigned_by_id, is_active, created_at, updated_at)
        SELECT DISTINCT ON (te.student_id, at.academic_year_id)
            gen_random_uuid(),
            te.school_id,
            te.student_id,
            te.class_id,
            at.academic_year_id,
            te.enrolled_by_id,
            te.is_active,
            te.created_at,
            te.updated_at
        FROM term_enrollment te
        JOIN academic_term at ON at.id = te.academic_term_id
        ORDER BY te.student_id, at.academic_year_id, te.created_at DESC
    """)

    op.drop_index('ix_term_enrollment_class_id', table_name='term_enrollment', if_exists=True)
    op.drop_column('term_enrollment', 'class_id')


def downgrade() -> None:
    op.add_column(
        'term_enrollment',
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Restore class_id from student_class_assignment
    op.execute("""
        UPDATE term_enrollment te
        SET class_id = sca.class_id
        FROM academic_term at
        JOIN student_class_assignment sca
            ON sca.student_id = te.student_id
           AND sca.academic_year_id = at.academic_year_id
        WHERE at.id = te.academic_term_id
    """)

    op.alter_column('term_enrollment', 'class_id', nullable=False)
    op.create_index('ix_term_enrollment_class_id', 'term_enrollment', ['class_id'])

    op.drop_index('ix_student_class_assignment_class_id', table_name='student_class_assignment')
    op.drop_index('ix_student_class_assignment_student_id', table_name='student_class_assignment')
    op.drop_table('student_class_assignment')
