"""
A teacher's own weekly schedule — "what do I teach tomorrow?" — split out of
services/timetable.py (which owns the class-facing timetable CRUD) since this
is a distinct read-only concern: deriving a *staff member's* full week from
their own active SubjectTeacher rows, not editing a class's slots.
"""
from __future__ import annotations
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme, Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import DayOfWeek, SchoolPeriod
from app.schemas.timetable import ScheduleEntry
from app.services.academic_year import get_current_year
from app.services.student_display import _class_display_name

_DAY_ORDER = {d: i for i, d in enumerate(DayOfWeek)}


async def _staff_member_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    """Duplicated rather than imported — matches the established convention
    in core/teacher_scope.py/student_scope.py/housing_scope.py, each of
    which keeps its own private copy instead of cross-importing another
    module's underscore-prefixed helper."""
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user or user.is_superadmin:
        return None
    return user.staff_member_id


async def get_my_schedule(
    staff_id: uuid.UUID, academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> list[ScheduleEntry]:
    """The caller's own full weekly schedule (every day at once — a
    timetable is a recurring structure, not date-specific), derived from
    their own active SubjectTeacher rows this year. Serves both the "My
    Timetable" page and the dashboard's "tomorrow" card, which filters this
    same list to tomorrow's weekday."""
    rows = await db.execute(
        select(
            SchoolPeriod.day_of_week, SchoolPeriod.start_time, SchoolPeriod.end_time,
            TimetableSlot.class_id, TimetableSlot.subject_id,
        )
        .select_from(TimetableSlot)
        .join(
            SubjectTeacher,
            (SubjectTeacher.class_id == TimetableSlot.class_id)
            & (SubjectTeacher.subject_id == TimetableSlot.subject_id)
            & (SubjectTeacher.academic_year_id == TimetableSlot.academic_year_id),
        )
        .join(SchoolPeriod, SchoolPeriod.id == TimetableSlot.period_id)
        .where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.academic_year_id == academic_year_id,
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.is_active.is_(True),
        )
    )
    rows = list(rows)
    if not rows:
        return []

    class_ids = {r.class_id for r in rows}
    subject_ids = {r.subject_id for r in rows}
    class_rows = await db.execute(
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(Class.id.in_(class_ids))
    )
    classes_by_id = {
        cls.id: _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)
        for cls, prog_name in class_rows
    }
    subjects_by_id = {
        s.id: s.name for s in await db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))
    }

    entries = [
        ScheduleEntry(
            day_of_week=r.day_of_week, start_time=r.start_time, end_time=r.end_time,
            class_id=r.class_id, class_name=classes_by_id.get(r.class_id, "—"),
            subject_id=r.subject_id, subject_name=subjects_by_id.get(r.subject_id, "—"),
        )
        for r in rows
    ]
    entries.sort(key=lambda e: (_DAY_ORDER[e.day_of_week], e.start_time))
    return entries


async def resolve_my_schedule(
    user_id: uuid.UUID, academic_year_id: uuid.UUID | None, school_id: uuid.UUID, db: AsyncSession,
) -> list[ScheduleEntry]:
    """Router-facing entrypoint for get_my_schedule() — resolves the caller's
    staff_member_id and defaults academic_year_id to the school's current
    year when omitted."""
    resolved_year_id = academic_year_id
    if resolved_year_id is None:
        year = await get_current_year(school_id, db)
        if year is None:
            return []
        resolved_year_id = year.id
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return []
    return await get_my_schedule(staff_id, resolved_year_id, school_id, db)
