"""
Attendance read-only summaries and the teacher-scoped "my classes" picker.
Split out of services/attendance.py (marking) to stay under the 300-line cap.
"""
from __future__ import annotations
import uuid
from collections import defaultdict
from datetime import date as _date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import classes_for_scope, resolve_attendance_scope, year_for_term
from app.models.academic import AcademicTerm
from app.models.attendance import AttendanceRecord, SchoolCalendar
from app.models.students import StudentClassAssignment
from app.schemas.academic import ClassRead
from app.schemas.attendance import (
    AttendanceSummaryRead, CalendarDayRead, StudentAbsenceSummary, TodayStatusRead,
)
from app.services.attendance_shared import (
    _MARKABLE_TYPES, _status_str, check_class_in_attendance_scope,
)


async def get_summary(
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> AttendanceSummaryRead:
    term = await db.scalar(
        select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")

    year_id = await year_for_term(term_id, db)
    if year_id is not None:
        scope = await resolve_attendance_scope(user_id, year_id, db)
        if scope is not None:
            student_class_id = await db.scalar(
                select(StudentClassAssignment.class_id).where(
                    StudentClassAssignment.student_id == student_id,
                    StudentClassAssignment.academic_year_id == year_id,
                    StudentClassAssignment.is_active.is_(True),
                )
            )
            if student_class_id is None or student_class_id not in scope:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")

    total = await db.scalar(
        select(func.count())
        .select_from(SchoolCalendar)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
        )
    ) or 0

    # Single GROUP BY instead of 4 separate COUNT queries. Filtered by the same
    # day_type set as `total` above — a day reclassified after attendance was
    # marked on it (override_calendar_day / generate_calendar force=True) must
    # not keep counting once it's no longer markable, or the rate can drift
    # inconsistent with `total` (even exceed 100%).
    rows = await db.execute(
        select(AttendanceRecord.status, func.count().label("n"))
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
            AttendanceRecord.period_id.is_(None),
        )
        .group_by(AttendanceRecord.status)
    )
    counts = {_status_str(r.status): r.n for r in rows}
    present = counts.get("PRESENT", 0)
    absent  = counts.get("ABSENT", 0)
    late    = counts.get("LATE", 0)
    excused = counts.get("EXCUSED", 0)
    # PRESENT only — matches attendance_stats.py::compute_attendance_stats(),
    # the single definition report_card.py/transcript.py are built on. This
    # endpoint previously counted LATE/EXCUSED toward the numerator too,
    # so the same student's rate could genuinely disagree between the live
    # Attendance page and their report card for the same term.
    rate    = round(present / total * 100, 1) if total > 0 else 0.0

    return AttendanceSummaryRead(
        student_id=student_id,
        term_id=term_id,
        total_school_days=total,
        days_present=present,
        days_absent=absent,
        days_late=late,
        days_excused=excused,
        days_unmarked=total - present - absent - late - excused,
        attendance_rate=rate,
    )


async def get_today_status(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> TodayStatusRead:
    """Fast endpoint: today's calendar day + submitted record count for a class."""
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date == _date.today(),
        )
    )
    if cal is not None:
        await check_class_in_attendance_scope(class_id, cal.academic_term_id, user_id, db)
    is_markable = cal is not None and cal.day_type in _MARKABLE_TYPES
    record_count = 0
    if is_markable:
        record_count = await db.scalar(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(
                AttendanceRecord.school_calendar_id == cal.id,  # type: ignore[union-attr]
                AttendanceRecord.class_id == class_id,
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.period_id.is_(None),
            )
        ) or 0
    return TodayStatusRead(
        calendar_day=CalendarDayRead.model_validate(cal) if cal else None,
        is_markable=is_markable,
        record_count=record_count,
    )


async def get_class_summaries(
    class_id: uuid.UUID,
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[StudentAbsenceSummary]:
    """Bulk per-student absence counts for a class (one query, for inline display)."""
    term = await db.scalar(
        select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")
    await check_class_in_attendance_scope(class_id, term_id, user_id, db)

    total_days = await db.scalar(
        select(func.count())
        .select_from(SchoolCalendar)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
        )
    ) or 0

    # A student withdrawn/transferred out of this class mid-term (row
    # deactivated, not deleted, by student_lifecycle.py) must not linger in
    # their old class teacher's absence summary — same stale-row shape as
    # the report-card ranking bug fixed in 12u.
    year_id = await year_for_term(term_id, db)
    active_student_ids: set[uuid.UUID] | None = None
    if year_id is not None:
        active_student_ids = set(await db.scalars(
            select(StudentClassAssignment.student_id).where(
                StudentClassAssignment.class_id == class_id,
                StudentClassAssignment.academic_year_id == year_id,
                StudentClassAssignment.is_active.is_(True),
            )
        ))

    query = (
        select(AttendanceRecord.student_id, AttendanceRecord.status, func.count().label("n"))
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
            AttendanceRecord.period_id.is_(None),
        )
    )
    if active_student_ids is not None:
        query = query.where(AttendanceRecord.student_id.in_(active_student_ids))
    rows = await db.execute(query.group_by(AttendanceRecord.student_id, AttendanceRecord.status))

    data: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for r in rows:
        data[r.student_id][_status_str(r.status)] = r.n

    result: list[StudentAbsenceSummary] = []
    for sid, counts in data.items():
        present = counts.get("PRESENT", 0)
        absent  = counts.get("ABSENT", 0)
        late    = counts.get("LATE", 0)
        # PRESENT only — see the matching comment in get_summary() above.
        rate    = round(present / total_days * 100, 1) if total_days > 0 else 0.0
        result.append(StudentAbsenceSummary(
            student_id=sid,
            days_absent=absent,
            days_late=late,
            attendance_rate=rate,
        ))
    return result


async def list_my_classes(
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassRead]:
    """Classes the caller can mark attendance for — every class in the
    school if unrestricted, else just their own ClassTeacher assignment(s).
    Powers the Attendance page's class picker."""
    year_id = await year_for_term(term_id, db)
    if year_id is None:
        return await classes_for_scope(None, school_id, db)
    scope = await resolve_attendance_scope(user_id, year_id, db)
    return await classes_for_scope(scope, school_id, db)
