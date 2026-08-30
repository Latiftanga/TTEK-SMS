"""
School-wide period-level "who's marked, who hasn't" oversight — the
period-level sibling of attendance_summary.py::get_marking_status(), split
into its own file since that one is already at the 300-line cap.

Only ever returns rows for (class, period) pairs that actually have a
TimetableSlot — nothing to mark otherwise, same "must be timetabled" rule
services/attendance_periods.py::list_markable_periods() enforces for the
single-class picker this oversight view is the school-wide sibling of.
Returns [] outright when the school hasn't opted into period-level
attendance at all, so the frontend can render nothing rather than an empty
state that implies the feature exists.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import classes_for_scope, resolve_attendance_scope, year_for_term
from app.models.academic import Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import AttendanceRecord, DayOfWeek, SchoolCalendar, SchoolPeriod
from app.models.school import School
from app.models.staff import StaffMember
from app.schemas.attendance import PeriodMarkingStatusRead
from app.services.staff import _display_name as _staff_display_name

_DAYS_IN_ORDER = list(DayOfWeek)


async def get_period_marking_status(
    calendar_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> list[PeriodMarkingStatusRead]:
    school = await db.get(School, school_id)
    if not school or not school.has_period_attendance:
        return []

    cal = await db.get(SchoolCalendar, calendar_id)
    if not cal or cal.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar day not found.")

    day_of_week = _DAYS_IN_ORDER[cal.date.weekday()]
    periods = list(await db.scalars(
        select(SchoolPeriod).where(
            SchoolPeriod.school_id == school_id, SchoolPeriod.day_of_week == day_of_week,
        )
    ))
    if not periods:
        return []
    period_by_id = {p.id: p for p in periods}

    year_id = await year_for_term(cal.academic_term_id, db)
    if year_id is None:
        return []

    scope = await resolve_attendance_scope(user_id, year_id, db)
    classes = await classes_for_scope(scope, school_id, db)
    if not classes:
        return []
    class_by_id = {c.id: c for c in classes}
    class_ids = list(class_by_id)

    slots = list(await db.scalars(
        select(TimetableSlot).where(
            TimetableSlot.class_id.in_(class_ids),
            TimetableSlot.period_id.in_(period_by_id),
            TimetableSlot.academic_year_id == year_id,
        )
    ))
    if not slots:
        return []

    subject_ids = {s.subject_id for s in slots}
    subjects_by_id = {
        s.id: s.name for s in await db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))
    }

    teacher_rows = await db.execute(
        select(
            SubjectTeacher.class_id, SubjectTeacher.subject_id,
            StaffMember.first_name, StaffMember.middle_name, StaffMember.last_name,
        )
        .join(StaffMember, StaffMember.id == SubjectTeacher.staff_member_id)
        .where(
            SubjectTeacher.class_id.in_(class_ids),
            SubjectTeacher.subject_id.in_(subject_ids),
            SubjectTeacher.academic_year_id == year_id,
            SubjectTeacher.is_active.is_(True),
        )
    )
    teacher_by_pair: dict[tuple[uuid.UUID, uuid.UUID], str] = {
        (class_id, subject_id): _staff_display_name(first, middle, last)
        for class_id, subject_id, first, middle, last in teacher_rows
    }

    marked_pairs = {
        (r.class_id, r.period_id)
        for r in await db.execute(
            select(AttendanceRecord.class_id, AttendanceRecord.period_id).where(
                AttendanceRecord.school_calendar_id == calendar_id,
                AttendanceRecord.class_id.in_(class_ids),
                AttendanceRecord.period_id.in_(period_by_id),
            ).distinct()
        )
    }

    result = [
        PeriodMarkingStatusRead(
            class_id=slot.class_id,
            class_name=class_by_id[slot.class_id].display_name,
            period_id=slot.period_id,
            period_name=period_by_id[slot.period_id].name,
            start_time=period_by_id[slot.period_id].start_time,
            end_time=period_by_id[slot.period_id].end_time,
            subject_name=subjects_by_id.get(slot.subject_id, "—"),
            teacher_name=teacher_by_pair.get((slot.class_id, slot.subject_id)),
            marked=(slot.class_id, slot.period_id) in marked_pairs,
        )
        for slot in slots
    ]
    # Unmarked first, then chronological, then by class — the periods
    # needing follow-up float to the top, matching get_marking_status()'s
    # own "unmarked first" convention.
    result.sort(key=lambda r: (r.marked, r.start_time, r.class_name))
    return result
