"""teacher position becomes derived from category, not manually assigned

Revision ID: d4e8f2a91c37
Revises: 7c9d490f63c4
Create Date: 2026-08-16 16:35:00.000000

TEACHER stops being a manually assignable/removable "responsibility" —
being a teacher is the core role, not an optional add-on like Class
Teacher/Housemaster/Headmaster. It is now auto-derived by
core/permissions.py::resolve_permissions() from
StaffCategory.staff_type == TEACHING (the same "Employment > Category"
field already set on every staff member at creation), mirroring how
CLASS_TEACHER/HOUSEMASTER are already derived from real ClassTeacher/
HouseMaster assignment rows rather than manually picked.

This migration only removes the now-redundant DIRECT staff_member_positions
links to the TEACHER position — the TEACHER StaffPosition row itself (and
its PositionPermission grants) is untouched, since resolve_permissions()
still looks it up by code exactly like it already does for CLASS_TEACHER/
HOUSEMASTER. Checked against the live dev DB before writing this: exactly 2
staff held TEACHER directly, both already category=TEACHING, so removing
the direct link changes nothing about their resolved permissions — they
keep TEACHER access via derivation instead.

Any staff member whose category is NOT "Teaching" but who held a direct
TEACHER link (none existed on the live dev DB, but possible elsewhere) will
lose TEACHER-derived permissions after this migration unless their category
is corrected — this is the intended behavior, not a bug: TEACHER access is
meant to track the Teaching/Non-Teaching classification now, per the
product decision this migration implements.

Downgrade is best-effort/lossy, like c2d3e4f5a6b7 and other position-cleanup
migrations before it: it cannot know which staff had TEACHER manually
picked before this migration (that information is gone), so it re-grants a
direct link to every currently-active staff member whose category is
TEACHING — an approximation of the pre-migration state, not a true restore.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8f2a91c37'
down_revision: Union[str, None] = '7c9d490f63c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM staff_member_positions
        WHERE position_id IN (SELECT id FROM staff_position WHERE code = 'TEACHER')
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO staff_member_positions (staff_member_id, position_id)
        SELECT sm.id, sp.id
        FROM staff_member sm
        JOIN staff_category sc ON sc.id = sm.category_id
        CROSS JOIN LATERAL (
            SELECT id FROM staff_position
            WHERE code = 'TEACHER'
              AND (school_id = sm.school_id OR school_id IS NULL)
            ORDER BY school_id NULLS LAST
            LIMIT 1
        ) sp
        WHERE sc.staff_type = 'TEACHING' AND sm.is_active = true
        ON CONFLICT DO NOTHING
    """))
