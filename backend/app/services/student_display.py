"""
Shared read-only display helpers — pure formatting (no DB access, except
_get_class_map) reused by student.py, student_list.py, student_export.py,
student_custom_export.py, and services/portal.py.

Split out of student.py (was over the 300-line cap).
"""
from __future__ import annotations
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.academic import Class, SHSProgramme
from app.models.students import StudentClassAssignment


def _display_name(first: str, middle: str | None, last: str) -> str:
    parts = [first]
    if middle:
        parts.append(middle)
    parts.append(last)
    return " ".join(parts)


def _class_display_name(level: str, year_group: int, programme: str | None, stream: str | None) -> str:
    if level.upper() == "SHS":
        # SHS: "1 General Science A" — level is implied by the school
        parts = [str(year_group)]
        if programme:
            parts.append(programme)
    elif level.upper() == "CRECHE":
        # Creche has no numbered year groups — just "Creche" (or "Creche A" with a stream)
        parts = [level]
    else:
        # Other basic levels: "Basic 5", "KG 2", etc.
        parts = [level, str(year_group)]
    if stream:
        parts.append(stream)
    return " ".join(parts)


def _photo_url(photo_path: str | None) -> str | None:
    """Convert a stored photo path to an absolute URL the frontend can use."""
    if not photo_path:
        return None
    if settings.storage_backend == "CLOUDFLARE_R2":
        return f"{settings.r2_public_url.rstrip('/')}/{photo_path}"
    return f"{settings.app_base_url.rstrip('/')}/uploads/{photo_path}"


def _active_class_assignment_subquery():
    """Most-recent active StudentClassAssignment per student.

    A promoted (not graduated/withdrawn) student is never deactivated from their
    prior year's assignment, so 2+ is_active=True rows can coexist for one student.
    DISTINCT ON collapses that to exactly one row per student, keeping this join
    provably 1:1 wherever it's used (list_students' count/sort, and here).
    """
    return (
        select(
            StudentClassAssignment.student_id,
            StudentClassAssignment.class_id,
            StudentClassAssignment.academic_year_id,
        )
        .where(StudentClassAssignment.is_active == True)  # noqa: E712
        .distinct(StudentClassAssignment.student_id)
        .order_by(StudentClassAssignment.student_id, StudentClassAssignment.created_at.desc())
        .subquery()
    )


async def _get_class_map(
    student_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict[uuid.UUID, tuple[str, int, str | None, str | None, uuid.UUID]]:
    if not student_ids:
        return {}
    active_sca = _active_class_assignment_subquery()
    rows = await db.execute(
        select(
            active_sca.c.student_id,
            Class.level,
            Class.year_group,
            Class.stream,
            SHSProgramme.name.label("programme_name"),
            Class.id.label("class_id"),
        )
        .join(Class, Class.id == active_sca.c.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(active_sca.c.student_id.in_(student_ids))
    )
    return {
        r.student_id: (r.level, r.year_group, r.programme_name, r.stream, r.class_id)
        for r in rows
    }
