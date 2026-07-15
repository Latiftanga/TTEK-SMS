"""
Attendance recording and per-student summary.

MARKING RULES
-------------
- school_calendar.day_type must be SCHOOL_DAY, EXAM_DAY, or HALF_DAY.
- Re-submitting attendance for the same student+calendar+period updates the record.
- period_id is NULL for daily (whole-day) attendance; non-NULL for period-level.
"""
from __future__ import annotations
import uuid
from collections import defaultdict
from datetime import date as _date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import (
    AttendanceRecord, AttendanceStatus, DayType, SchoolCalendar,
)
from app.models.school import School
from app.schemas.attendance import (
    AttendanceMarkRequest, AttendanceRecordRead, AttendanceSummaryRead,
    CalendarDayRead, StudentAbsenceSummary, TodayStatusRead,
)
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc

_MARKABLE_TYPES = {DayType.SCHOOL_DAY, DayType.EXAM_DAY, DayType.HALF_DAY}


def _to_read(r: AttendanceRecord) -> AttendanceRecordRead:
    return AttendanceRecordRead.model_validate(r)


def _status_str(val: object) -> str:
    return val.value if hasattr(val, "value") else str(val)


async def mark_attendance(
    req: AttendanceMarkRequest,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[AttendanceRecordRead]:
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.id == req.school_calendar_id,
            SchoolCalendar.school_id == school_id,
        )
    )
    if not cal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar day not found.")
    if cal.day_type not in _MARKABLE_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cannot mark attendance on a {cal.day_type.value} day.",
        )

    now = datetime.now(timezone.utc)
    saved: list[AttendanceRecord] = []
    new_absent_ids: set = set()   # student_ids that are newly marked ABSENT (not re-marks)

    for mark in req.records:
        existing = await db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == mark.student_id,
                AttendanceRecord.school_calendar_id == req.school_calendar_id,
                AttendanceRecord.period_id.is_(None),
            )
        )
        if existing:
            existing.status = mark.status
            existing.notes = mark.notes
            existing.recorded_by_id = user_id
            existing.recorded_at = now
            saved.append(existing)
        else:
            rec = AttendanceRecord(
                school_id=school_id,
                student_id=mark.student_id,
                school_calendar_id=req.school_calendar_id,
                class_id=req.class_id,
                status=mark.status,
                notes=mark.notes,
                recorded_by_id=user_id,
                recorded_at=now,
            )
            db.add(rec)
            saved.append(rec)
            if mark.status == AttendanceStatus.ABSENT:
                new_absent_ids.add(mark.student_id)

    await db.flush()

    # Fire absence alerts only for NEW ABSENT marks — never on re-marks
    if new_absent_ids:
        school = await db.get(School, school_id)
        school_short = (school.short_name or school.name) if school else ""
        absence_date = cal.date.isoformat()
        for rec, mark in zip(saved, req.records):
            if mark.student_id in new_absent_ids:
                await sms_svc.notify_attendance_absent(
                    student_id=mark.student_id,
                    school_id=school_id,
                    school_short=school_short,
                    absence_date=absence_date,
                    entity_id=rec.id,
                    db=db,
                )
                await email_svc.notify_attendance_absent_email(
                    student_id=mark.student_id,
                    school_id=school_id,
                    school_short=school_short,
                    absence_date=absence_date,
                    entity_id=rec.id,
                    db=db,
                )

    return [_to_read(r) for r in saved]


async def list_attendance(
    school_calendar_id: uuid.UUID,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[AttendanceRecordRead]:
    rows = await db.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.school_calendar_id == school_calendar_id,
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.period_id.is_(None),
        ).order_by(AttendanceRecord.recorded_at)
    )
    return [_to_read(r) for r in rows]


async def get_summary(
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> AttendanceSummaryRead:
    total = await db.scalar(
        select(func.count())
        .select_from(SchoolCalendar)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
        )
    ) or 0

    # Single GROUP BY instead of 4 separate COUNT queries
    rows = await db.execute(
        select(AttendanceRecord.status, func.count().label("n"))
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            AttendanceRecord.period_id.is_(None),
        )
        .group_by(AttendanceRecord.status)
    )
    counts = {_status_str(r.status): r.n for r in rows}
    present = counts.get("PRESENT", 0)
    absent  = counts.get("ABSENT", 0)
    late    = counts.get("LATE", 0)
    excused = counts.get("EXCUSED", 0)
    rate    = round((present + late + excused) / total * 100, 1) if total > 0 else 0.0

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
    db: AsyncSession,
) -> TodayStatusRead:
    """Fast endpoint: today's calendar day + submitted record count for a class."""
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date == _date.today(),
        )
    )
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
    db: AsyncSession,
) -> list[StudentAbsenceSummary]:
    """Bulk per-student absence counts for a class (one query, for inline display)."""
    total_days = await db.scalar(
        select(func.count())
        .select_from(SchoolCalendar)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in _MARKABLE_TYPES]),
        )
    ) or 0

    rows = await db.execute(
        select(AttendanceRecord.student_id, AttendanceRecord.status, func.count().label("n"))
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            AttendanceRecord.period_id.is_(None),
        )
        .group_by(AttendanceRecord.student_id, AttendanceRecord.status)
    )

    data: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for r in rows:
        data[r.student_id][_status_str(r.status)] = r.n

    result: list[StudentAbsenceSummary] = []
    for sid, counts in data.items():
        present = counts.get("PRESENT", 0)
        absent  = counts.get("ABSENT", 0)
        late    = counts.get("LATE", 0)
        excused = counts.get("EXCUSED", 0)
        rate    = round((present + late + excused) / total_days * 100, 1) if total_days > 0 else 0.0
        result.append(StudentAbsenceSummary(
            student_id=sid,
            days_absent=absent,
            days_late=late,
            attendance_rate=rate,
        ))
    return result
