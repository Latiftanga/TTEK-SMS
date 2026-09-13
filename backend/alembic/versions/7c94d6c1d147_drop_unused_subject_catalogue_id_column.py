"""drop unused subject catalogue_id column

Revision ID: 7c94d6c1d147
Revises: b0f2e3d4c5a6
Create Date: 2026-09-13 14:21:58.639837

The "adopt a subject from the GES national catalogue" feature was dead code:
nothing anywhere ever created a SubjectCatalogue row for this purpose, so
GET /academic/catalogue always returned [] and the frontend's "From
catalogue" tab was permanently empty in every real deployment. Subject
creation is now always a plain code+name custom entry.

subject_catalogue itself is NOT dropped here — lesson_plans.CurriculumStandard
still has a live, non-nullable FK to it (a separate, unrelated feature) —
only Subject's own now-always-null catalogue_id link is removed.

Autogenerate also picked up several pre-existing, unrelated drift items
(stray indexes/constraints on ai_config, class, curriculum_material_chunk,
school, sms_log, student_class_assignment) — all stripped out of this
migration; they're out of scope for this change and each deserves its own
deliberate look rather than being silently bundled in here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c94d6c1d147'
down_revision: Union[str, None] = 'b0f2e3d4c5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('subject_catalogue_id_fkey', 'subject', type_='foreignkey')
    op.drop_column('subject', 'catalogue_id')


def downgrade() -> None:
    op.add_column('subject', sa.Column('catalogue_id', sa.UUID(), autoincrement=False, nullable=True))
    op.create_foreign_key('subject_catalogue_id_fkey', 'subject', 'subject_catalogue', ['catalogue_id'], ['id'])
