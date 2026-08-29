"""
Attendance trend series (day-by-day rate over a term) and the per-student
export used by both the Trends tab's "Export" button and, in principle, any
other GES-reporting need. Both are scoped exactly like every other
attendance read (resolve_attendance_scope / check_class_in_attendance_scope)
— an admin/attendance.approve holder sees the whole school, a scoped
class-teacher only their own class(es).

Unlike get_class_summaries (one class at a time), these two functions can
span every class in scope at once — the "whole school" trend/export case a
Trends tab needs, not just a single-class summary.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import resolve_attendance_scope
from app.models.academic import AcademicTerm
from app.models.attendance import AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.students import Student, StudentClassAssignment
from app.schemas.attendance_trends import AttendanceTrendPoint
from app.services.attendance_shared import _MARKABLE_TYPES, check_class_in_attendance_scope
from app.services.student_display import _class_display_name, _get_class_map


async def _resolve_scoped_student_ids(
    term: AcademicTerm, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
    class_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    if class_id is not None:
        await check_class_in_attendance_scope(class_id, term.id, user_id, db)
        class_ids: list[uuid.UUID] | None = [class_id]
    else:
        scope = await resolve_attendance_scope(user_id, term.academic_year_id, db)
        class_ids = list(scope) if scope is not None else None

    q = select(StudentClassAssignment.student_id).where(
        StudentClassAssignment.school_id == school_id,
        StudentClassAssignment.academic_year_id == term.academic_year_id,
        StudentClassAssignment.is_active.is_(True),
    )
    if class_ids is not None:
        if not class_ids:
            return []
        q = q.where(StudentClassAssignment.class_id.in_(class_ids))
    return list(await db.scalars(q))


async def _get_term(term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm:
    term = await db.scalar(
        select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")
    return term


async def get_attendance_trend(
    term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
    class_id: uuid.UUID | None = None,
) -> list[AttendanceTrendPoint]:
    term = await _get_term(term_id, school_id, db)
    student_ids = await _resolve_scoped_student_ids(term, school_id, user_id, db, class_id)
    total_active = len(student_ids)
    if total_active == 0:
        return []

    markable = [t.value for t in _MARKABLE_TYPES]
    dates = list(await db.scalars(
        select(SchoolCalendar.date)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_(markable),
        )
        .order_by(SchoolCalendar.date)
    ))
    if not dates:
        return []

    present_rows = await db.execute(
        select(SchoolCalendar.date, func.count(AttendanceRecord.id).label("present"))
        .join(AttendanceRecord, AttendanceRecord.school_calendar_id == SchoolCalendar.id)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_(markable),
            AttendanceRecord.status == AttendanceStatus.PRESENT,
            AttendanceRecord.period_id.is_(None),
            AttendanceRecord.student_id.in_(student_ids),
        )
        .group_by(SchoolCalendar.date)
    )
    present_map = {r.date: r.present for r in present_rows}

    return [
        AttendanceTrendPoint(
            date=d, present=present_map.get(d, 0), total=total_active,
            rate=round(present_map.get(d, 0) / total_active * 100, 1),
        )
        for d in dates
    ]


async def get_attendance_export_rows(
    term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
    class_id: uuid.UUID | None = None,
) -> tuple[list[str], list[list[str]]]:
    headers = ["Admission Number", "Name", "Class", "Present", "Absent", "Late", "Excused", "Attendance Rate (%)"]

    term = await _get_term(term_id, school_id, db)
    student_ids = await _resolve_scoped_student_ids(term, school_id, user_id, db, class_id)
    if not student_ids:
        return headers, []

    markable = [t.value for t in _MARKABLE_TYPES]
    total_days = await db.scalar(
        select(func.count()).select_from(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_(markable),
        )
    ) or 0

    status_rows = await db.execute(
        select(AttendanceRecord.student_id, AttendanceRecord.status, func.count().label("n"))
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id.in_(student_ids),
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.period_id.is_(None),
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_(markable),
        )
        .group_by(AttendanceRecord.student_id, AttendanceRecord.status)
    )
    counts: dict[uuid.UUID, dict[str, int]] = {}
    for r in status_rows:
        counts.setdefault(r.student_id, {})[r.status.value] = r.n

    students = list(await db.scalars(
        select(Student).where(Student.id.in_(student_ids)).order_by(Student.last_name, Student.first_name)
    ))
    class_map = await _get_class_map(student_ids, db)

    rows: list[list[str]] = []
    for s in students:
        c = counts.get(s.id, {})
        present, absent, late, excused = c.get("PRESENT", 0), c.get("ABSENT", 0), c.get("LATE", 0), c.get("EXCUSED", 0)
        rate = round(present / total_days * 100, 1) if total_days else 0.0
        level, year_group, programme, stream, _cls_id = class_map.get(s.id, (None, 0, None, None, None))
        class_name = _class_display_name(level, year_group, programme, stream) if level else ""
        rows.append([
            s.admission_number, f"{s.first_name} {s.last_name}", class_name,
            str(present), str(absent), str(late), str(excused), f"{rate}",
        ])
    return headers, rows
