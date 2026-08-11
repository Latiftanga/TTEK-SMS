"""Custom-field staff export — CSV, Excel, or PDF.

Caller selects which columns to include from STAFF_FIELDS.
All standard filter params (search, gender, category_id, active_only) are respected.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.staff import StaffMember
from app.models.staff_history import StaffPromotion
from app.services.export_utils import rows_to_bytes
from app.services.staff_query import staff_search_condition


def _full_name(m: StaffMember) -> str:
    parts = [m.last_name, m.first_name]
    if m.middle_name:
        parts.append(m.middle_name)
    return ", ".join(parts[:1]) + " " + " ".join(parts[1:])


def _current_rank(m: StaffMember) -> str:
    if not m.promotions:
        return "—"
    latest = sorted(m.promotions, key=lambda p: p.effective_date, reverse=True)[0]
    return latest.to_rank.title if latest.to_rank else "—"


type _Extractor = Callable[[StaffMember], str]

STAFF_FIELDS: dict[str, tuple[str, _Extractor]] = {
    "staff_number":    ("Staff No.",        lambda m: m.staff_number),
    "full_name":       ("Full Name",         lambda m: _full_name(m)),
    "first_name":      ("First Name",        lambda m: m.first_name),
    "last_name":       ("Last Name",         lambda m: m.last_name),
    "gender":          ("Gender",            lambda m: m.gender.value if m.gender else ""),
    "date_of_birth":   ("Date of Birth",     lambda m: str(m.date_of_birth) if m.date_of_birth else ""),
    "category":        ("Job Class",         lambda m: m.category.name if m.category else ""),
    "positions":       ("Position(s)",       lambda m: "; ".join(p.name for p in m.positions)),
    "employment_type": ("Employment Type",   lambda m: m.employment_type.value if m.employment_type else ""),
    "joined_date":     ("Date Joined",       lambda m: m.joined_date.isoformat() if m.joined_date else ""),
    "current_rank":    ("Current Rank",      lambda m: _current_rank(m)),
    "ssnit_number":    ("SSNIT No.",         lambda m: m.ssnit_number or ""),
    "national_id":     ("Ghana Card No.",    lambda m: m.national_id or ""),
    "phone":           ("Phone",             lambda m: m.phone or ""),
    "email":           ("Email",             lambda m: m.email or ""),
    "status":          ("Status",            lambda m: "Active" if m.is_active else "Inactive"),
}


async def export_staff_custom(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    fields: list[str],
    fmt: str = "csv",
    active_only: bool = True,
    category_id: uuid.UUID | None = None,
    search: str | None = None,
    gender: str | None = None,
) -> bytes:
    resolved = [(k, STAFF_FIELDS[k]) for k in fields if k in STAFF_FIELDS]
    if not resolved:
        resolved = list(STAFF_FIELDS.items())

    q = (
        select(StaffMember)
        .where(StaffMember.school_id == school_id)
        .options(
            selectinload(StaffMember.category),
            selectinload(StaffMember.positions),
            selectinload(StaffMember.promotions).selectinload(StaffPromotion.to_rank),
        )
        .order_by(StaffMember.last_name, StaffMember.first_name)
    )
    if active_only:
        q = q.where(StaffMember.is_active == True)  # noqa: E712
    if category_id:
        q = q.where(StaffMember.category_id == category_id)
    if gender:
        q = q.where(StaffMember.gender == gender)
    if search:
        q = q.where(staff_search_condition(search))
    members = list(await db.scalars(q))

    headers = [label for _, (label, _) in resolved]
    data_rows = [
        [extractor(m) for _, (_lbl, extractor) in resolved]
        for m in members
    ]

    if fmt == "pdf":
        from app.services.pdf import render_export_table
        school = await db.get(School, school_id)
        return render_export_table(
            school, "Staff Register", headers, data_rows,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            total=len(data_rows),
        )
    return rows_to_bytes(headers, data_rows, fmt, sheet_title="Staff")
