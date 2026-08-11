"""Shared staff text-search clause.

Used by list_staff (services/staff.py, the on-screen list) and the custom
export path (staff_custom_export.py) so a search term always matches the
exact same fields everywhere — name, staff number, category name, and
position name. Before this was shared, the export path only matched name/
staff number: searching by a position or category name (e.g. "Bursar")
showed matching staff on screen but the export of "what's filtered"
silently dropped them, since none of their literal names contained the
search term.
"""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

from app.models.auth import StaffPosition
from app.models.staff import StaffCategory, StaffMember


def staff_search_condition(search: str) -> ColumnElement[bool]:
    s = f"%{search}%"
    return or_(
        StaffMember.first_name.ilike(s),
        StaffMember.last_name.ilike(s),
        StaffMember.staff_number.ilike(s),
        StaffMember.category.has(StaffCategory.name.ilike(s)),
        StaffMember.positions.any(StaffPosition.name.ilike(s)),
    )
