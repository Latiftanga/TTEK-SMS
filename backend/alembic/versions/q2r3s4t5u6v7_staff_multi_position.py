"""Staff multi-position: replace position_id FK with staff_member_positions junction table.

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-06-16

Changes:
- Drop staff_member.position_id column
- Drop staff_member.department column
- Create staff_member_positions junction table (many-to-many)
- Replace CLASS_TEACHER + SUBJECT_TEACHER seeded templates with TEACHER
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("staff_member", "position_id")
    op.drop_column("staff_member", "department")

    op.create_table(
        "staff_member_positions",
        sa.Column("staff_member_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff_member.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("position_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff_position.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # Replace CLASS_TEACHER + SUBJECT_TEACHER templates with a single TEACHER template.
    # We delete rows then re-insert rather than UPDATE so that permission rows
    # referencing the old position_ids are also cleaned up.
    conn = op.get_bind()

    # Remove permission rows for the two positions being retired
    conn.execute(sa.text("""
        DELETE FROM position_permission
        WHERE position_id IN (
            SELECT id FROM staff_position
            WHERE code IN ('CLASS_TEACHER', 'SUBJECT_TEACHER')
            AND school_id IS NULL
        )
    """))
    # Remove the template positions themselves
    conn.execute(sa.text("""
        DELETE FROM staff_position
        WHERE code IN ('CLASS_TEACHER', 'SUBJECT_TEACHER')
        AND school_id IS NULL
    """))

    # Insert TEACHER template if it doesn't already exist
    conn.execute(sa.text("""
        INSERT INTO staff_position (id, code, name, is_template, is_active, school_id, created_at, updated_at)
        SELECT gen_random_uuid(), 'TEACHER', 'Teacher', TRUE, TRUE, NULL, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM staff_position WHERE code = 'TEACHER' AND school_id IS NULL
        )
    """))

    # Add TEACHER permissions (union of former CLASS_TEACHER + SUBJECT_TEACHER sets)
    conn.execute(sa.text("""
        INSERT INTO position_permission (id, position_id, module, action, is_allowed)
        SELECT gen_random_uuid(), sp.id, t.module, t.action, TRUE
        FROM staff_position sp,
        (VALUES
            ('school',       'view'),
            ('students',     'view'),
            ('students',     'create'),
            ('students',     'edit'),
            ('academic',     'view'),
            ('attendance',   'view'),
            ('attendance',   'record'),
            ('assessments',  'view'),
            ('assessments',  'enter_scores'),
            ('fees',         'view'),
            ('reports',      'view')
        ) AS t(module, action)
        WHERE sp.code = 'TEACHER' AND sp.school_id IS NULL
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    op.drop_table("staff_member_positions")

    op.add_column("staff_member",
        sa.Column("department", sa.String(100), nullable=True))
    op.add_column("staff_member",
        sa.Column("position_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff_position.id"), nullable=True))

    conn = op.get_bind()
    # Remove TEACHER template and its permissions
    conn.execute(sa.text("""
        DELETE FROM position_permission
        WHERE position_id IN (
            SELECT id FROM staff_position WHERE code = 'TEACHER' AND school_id IS NULL
        )
    """))
    conn.execute(sa.text("""
        DELETE FROM staff_position WHERE code = 'TEACHER' AND school_id IS NULL
    """))
