"""
Period-level attendance picker — "which periods can I mark attendance for,
on this class, on this calendar day?" Additive to daily (whole-day) marking;
see services/attendance.py::mark_attendance()'s own period_id branch for the
write path this powers.

Only periods with an assigned TimetableSlot are offered at all — a period
with nothing scheduled has no lesson to take attendance for. can_mark
mirrors services/attendance_shared.py::check_period_attendance_scope()'s
rule exactly (unrestricted attendance.approve holder, this year's
ClassTeacher, or that specific period's SubjectTeacher) but as a per-period
boolean rather than a raised exception, since the picker needs to show a
disabled-not-hidden option for a period the caller can't mark.
"""
from __future__ import annotations
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import resolve_attendance_scope, year_for_term
from app.models.academic import Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import AttendanceRecord, DayOfWeek, SchoolCalendar, SchoolPeriod
from app.models.school import School
from app.models.staff import StaffMember
from app.schemas.attendance import MarkablePeriod
from app.services.attendance_shared import _staff_member_id_for
from app.services.staff import _display_name as _staff_display_name

_DAYS_IN_ORDER = list(DayOfWeek)


async def list_markable_periods(
    class_id: uuid.UUID,
    school_calendar_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[MarkablePeriod]:
    school = await db.get(School, school_id)
    if not school or not school.has_period_attendance:
        return []

    cal = await db.get(SchoolCalendar, school_calendar_id)
    if not cal or cal.school_id != school_id:
        return []

    day_of_week = _DAYS_IN_ORDER[cal.date.weekday()]
    periods = list(await db.scalars(
        select(SchoolPeriod)
        .where(SchoolPeriod.school_id == school_id, SchoolPeriod.day_of_week == day_of_week)
        .order_by(SchoolPeriod.period_number)
    ))
    if not periods:
        return []

    year_id = await year_for_term(cal.academic_term_id, db)
    if year_id is None:
        return []

    period_ids = [p.id for p in periods]
    slots = list(await db.scalars(
        select(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.academic_year_id == year_id,
            TimetableSlot.period_id.in_(period_ids),
        )
    ))
    slot_by_period = {s.period_id: s for s in slots}
    if not slot_by_period:
        return []

    subject_ids = {s.subject_id for s in slots}
    subjects_by_id = {
        s.id: s.name for s in await db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))
    }

    teacher_rows = await db.execute(
        select(
            SubjectTeacher.subject_id, SubjectTeacher.staff_member_id,
            StaffMember.first_name, StaffMember.middle_name, StaffMember.last_name,
        )
        .join(StaffMember, StaffMember.id == SubjectTeacher.staff_member_id)
        .where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.academic_year_id == year_id,
            SubjectTeacher.subject_id.in_(subject_ids),
            SubjectTeacher.is_active.is_(True),
        )
    )
    teacher_by_subject: dict[uuid.UUID, tuple[uuid.UUID, str]] = {
        subject_id: (staff_id, _staff_display_name(first, middle, last))
        for subject_id, staff_id, first, middle, last in teacher_rows
    }

    existing_period_ids = set(await db.scalars(
        select(AttendanceRecord.period_id).where(
            AttendanceRecord.school_calendar_id == school_calendar_id,
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.period_id.in_(period_ids),
        ).distinct()
    ))

    scope = await resolve_attendance_scope(user_id, year_id, db)
    class_teacher_ok = scope is None or class_id in scope
    caller_staff_id = await _staff_member_id_for(user_id, db)

    result: list[MarkablePeriod] = []
    for p in periods:
        slot = slot_by_period.get(p.id)
        if not slot:
            continue
        teacher_staff_id, teacher_name = teacher_by_subject.get(slot.subject_id, (None, None))
        can_mark = class_teacher_ok or (
            teacher_staff_id is not None and teacher_staff_id == caller_staff_id
        )
        result.append(MarkablePeriod(
            period_id=p.id,
            name=p.name,
            start_time=p.start_time,
            end_time=p.end_time,
            subject_id=slot.subject_id,
            subject_name=subjects_by_id.get(slot.subject_id, "—"),
            teacher_name=teacher_name,
            can_mark=can_mark,
            already_marked=p.id in existing_period_ids,
        ))
    return result
