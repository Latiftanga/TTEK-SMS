"""Shared student query-filter helpers.

Used by list_students (services/student_list.py, the on-screen list) and
the custom export path (student_custom_export.py) so a filter behaves
identically everywhere — same shape as services/staff_query.py.
"""
from __future__ import annotations
import uuid

from sqlalchemy import select
from sqlalchemy.sql.elements import ColumnElement

from app.models.documents import GraduationRecord, GraduationType
from app.models.students import Student


def graduated_condition(school_id: uuid.UUID, graduated: bool) -> ColumnElement[bool]:
    """Lifetime check, not scoped to one academic year — a student graduated
    in any past year still matches graduated=True."""
    graduated_ids = select(GraduationRecord.student_id).where(
        GraduationRecord.school_id == school_id,
        GraduationRecord.graduation_type == GraduationType.GRADUATED,
    )
    return Student.id.in_(graduated_ids) if graduated else Student.id.not_in(graduated_ids)
