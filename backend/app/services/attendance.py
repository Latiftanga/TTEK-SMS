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
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import (
    AttendanceRecord, AttendanceStatus, DayType, SchoolCalendar,
)
from app.schemas.attendance import (
    AttendanceMarkRequest, AttendanceRecordRead, AttendanceSummaryRead,
)

_MARKABLE_TYPES = {DayType.SCHOOL_DAY, DayType.EXAM_DAY, DayType.HALF_DAY}


def _to_read(r: AttendanceRecord) -> AttendanceRecordRead:
    return AttendanceRecordRead.model_validate(r)


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

    await db.flush()
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

    async def _count(s: AttendanceStatus) -> int:
        return await db.scalar(
            select(func.count())
            .select_from(AttendanceRecord)
            .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
            .where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.school_id == school_id,
                SchoolCalendar.academic_term_id == term_id,
                AttendanceRecord.status == s,
                AttendanceRecord.period_id.is_(None),
            )
        ) or 0

    present = await _count(AttendanceStatus.PRESENT)
    absent = await _count(AttendanceStatus.ABSENT)
    late = await _count(AttendanceStatus.LATE)
    excused = await _count(AttendanceStatus.EXCUSED)
    rate = round(present / total * 100, 1) if total > 0 else 0.0

    return AttendanceSummaryRead(
        student_id=student_id,
        term_id=term_id,
        total_school_days=total,
        days_present=present,
        days_absent=absent,
        days_late=late,
        days_excused=excused,
        attendance_rate=rate,
    )
