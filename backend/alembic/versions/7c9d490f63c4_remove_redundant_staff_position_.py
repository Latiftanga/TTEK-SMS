"""remove redundant staff position templates

Revision ID: 7c9d490f63c4
Revises: b32464027d23
Create Date: 2026-08-16 11:20:57.873999

Removes 6 seeded StaffPosition templates (DEPUTY_HEAD,
ASSISTANT_HEAD_ACADEMICS, ASSISTANT_HEAD_ADMINISTRATION,
ASSISTANT_HEAD_BOARDING, HOD, EXAM_OFFICER) — redundant with the
already-existing per-staff-member personal permission override
(StaffPermission, admin/staff/[id] > Permissions), which already lets an
admin grant any staff member exactly the permissions their real delegated
authority covers, without a nationwide-fixed preset standing in for a title
that in practice varies school to school. HEAD/TEACHER/BURSAR (manually
assigned) and CLASS_TEACHER/HOUSEMASTER (auto-derived from real
ClassTeacher/HouseMaster assignment rows — see
core/permissions.py::resolve_permissions) are untouched.

Scoped to school_id IS NULL throughout, same convention as
q2r3s4t5u6v7_staff_multi_position.py: a school that had already forked one
of these 6 codes for itself keeps its own copy untouched (none do on the
live dev DB, confirmed before writing this migration, but the migration is
written to be correct regardless).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c9d490f63c4'
down_revision: Union[str, None] = 'b32464027d23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOVED_CODES = (
    "DEPUTY_HEAD",
    "ASSISTANT_HEAD_ACADEMICS",
    "ASSISTANT_HEAD_ADMINISTRATION",
    "ASSISTANT_HEAD_BOARDING",
    "HOD",
    "EXAM_OFFICER",
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM position_permission
        WHERE position_id IN (
            SELECT id FROM staff_position
            WHERE code = ANY(:codes) AND school_id IS NULL
        )
    """), {"codes": list(REMOVED_CODES)})
    conn.execute(sa.text("""
        DELETE FROM staff_position
        WHERE code = ANY(:codes) AND school_id IS NULL
    """), {"codes": list(REMOVED_CODES)})


def downgrade() -> None:
    conn = op.get_bind()

    positions = [
        ("DEPUTY_HEAD", "Deputy Headmaster", [
            ("school", "view"), ("school", "edit"),
            ("staff", "view"), ("staff", "create"), ("staff", "edit"),
            ("students", "view"), ("students", "create"), ("students", "edit"), ("students", "delete"),
            ("academic", "view"), ("academic", "create"), ("academic", "edit"),
            ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
            ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
            ("assessments", "record_behaviour"),
            ("fees", "view"), ("fees", "collect"),
            ("housing", "view"), ("housing", "assign"),
            ("reports", "view"), ("reports", "generate"),
            ("documents", "view"), ("documents", "manage"),
        ]),
        ("ASSISTANT_HEAD_ACADEMICS", "Assistant Head (Academics)", [
            ("school", "view"),
            ("staff", "view"),
            ("students", "view"), ("students", "edit"), ("students", "delete"),
            ("academic", "view"), ("academic", "edit"),
            ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
            ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
            ("assessments", "record_behaviour"),
            ("reports", "view"), ("reports", "generate"),
            ("documents", "view"), ("documents", "manage"),
        ]),
        ("ASSISTANT_HEAD_ADMINISTRATION", "Assistant Head (Administration)", [
            ("school", "view"), ("school", "edit"),
            ("staff", "view"), ("staff", "create"), ("staff", "edit"),
            ("students", "view"),
            ("reports", "view"), ("reports", "generate"),
            ("documents", "view"), ("documents", "manage"),
        ]),
        ("ASSISTANT_HEAD_BOARDING", "Assistant Head (Domestic/Boarding)", [
            ("school", "view"),
            ("students", "view"),
            ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
            ("attendance", "view"), ("attendance", "record"),
            ("reports", "view"), ("reports", "generate"),
            ("documents", "view"), ("documents", "manage"),
        ]),
        ("HOD", "Head of Department", [
            ("school", "view"),
            ("staff", "view"),
            ("students", "view"), ("students", "edit"), ("students", "delete"),
            ("academic", "view"), ("academic", "edit"),
            ("attendance", "view"), ("attendance", "record"),
            ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
            ("assessments", "record_behaviour"),
            ("reports", "view"), ("reports", "generate"),
            ("documents", "view"), ("documents", "manage"),
        ]),
        ("EXAM_OFFICER", "Examination Officer", [
            ("school", "view"),
            ("students", "view"),
            ("academic", "view"), ("academic", "edit"),
            ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
            ("assessments", "record_behaviour"),
            ("reports", "view"), ("reports", "generate"),
            ("documents", "view"), ("documents", "manage"),
        ]),
    ]

    insert_position = sa.text("""
        INSERT INTO staff_position (id, code, name, is_template, is_active, school_id, created_at, updated_at)
        SELECT gen_random_uuid(), :code, :name, TRUE, TRUE, NULL, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM staff_position WHERE code = :code AND school_id IS NULL
        )
    """).bindparams(sa.bindparam("code", type_=sa.String), sa.bindparam("name", type_=sa.String))

    insert_permission = sa.text("""
        INSERT INTO position_permission (id, position_id, module, action, is_allowed)
        SELECT gen_random_uuid(), sp.id, :module, :action, TRUE
        FROM staff_position sp
        WHERE sp.code = :code AND sp.school_id IS NULL
        ON CONFLICT DO NOTHING
    """).bindparams(
        sa.bindparam("code", type_=sa.String),
        sa.bindparam("module", type_=sa.String),
        sa.bindparam("action", type_=sa.String),
    )

    for code, name, perms in positions:
        conn.execute(insert_position, {"code": code, "name": name})
        for module, action in perms:
            conn.execute(insert_permission, {"code": code, "module": module, "action": action})
