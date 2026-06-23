"""
Attendance router — school schedule, calendar, and attendance records.

Permission map:
  attendance.approve  → schedule management + calendar generation + overrides
  attendance.record   → mark attendance for a class
  attendance.view     → read records, summary (any authenticated staff)
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.schemas.attendance import (
    AttendanceMarkRequest, AttendanceRecordRead, AttendanceSummaryRead,
    CalendarDayOverride, CalendarDayRead, CalendarGenerateRequest,
    ScheduleRead, ScheduleUpsert, StudentAbsenceSummary, TodayStatusRead,
)
from app.services import attendance as att_svc
from app.services import attendance_calendar as cal_svc

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ── School schedule ───────────────────────────────────────────────────────────

@router.post("/schedule", response_model=ScheduleRead, status_code=201)
async def upsert_schedule(
    req: ScheduleUpsert,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return ScheduleRead.model_validate(await cal_svc.upsert_schedule(req, school_id, db))


@router.get("/schedule", response_model=list[ScheduleRead])
async def list_schedule(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return [ScheduleRead.model_validate(s) for s in await cal_svc.list_schedule(school_id, db)]


# ── School calendar ───────────────────────────────────────────────────────────

@router.post("/calendar/generate", response_model=list[CalendarDayRead], status_code=201)
async def generate_calendar(
    req: CalendarGenerateRequest,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    days = await cal_svc.generate_calendar(req, school_id, db)
    return [CalendarDayRead.model_validate(d) for d in days]


@router.get("/calendar", response_model=list[CalendarDayRead])
async def list_calendar(
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return [CalendarDayRead.model_validate(d) for d in await cal_svc.list_calendar(school_id, term_id, db)]


@router.patch("/calendar/{cal_id}", response_model=CalendarDayRead)
async def override_calendar_day(
    cal_id: uuid.UUID,
    req: CalendarDayOverride,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return CalendarDayRead.model_validate(
        await cal_svc.override_calendar_day(cal_id, req, school_id, db)
    )


# ── Attendance records ────────────────────────────────────────────────────────

@router.post("/mark", response_model=list[AttendanceRecordRead], status_code=201)
async def mark_attendance(
    req: AttendanceMarkRequest,
    ids=Depends(require_permission("attendance", "record")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await att_svc.mark_attendance(req, school_id, user_id, db)


@router.get("/records", response_model=list[AttendanceRecordRead])
async def list_attendance(
    calendar_id: uuid.UUID = Query(...),
    class_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await att_svc.list_attendance(calendar_id, class_id, school_id, db)


@router.get("/today", response_model=TodayStatusRead)
async def get_today_status(
    class_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Today's calendar status + existing record count for a class — single fast call."""
    _, school_id = ids
    return await att_svc.get_today_status(class_id, school_id, db)


@router.get("/class-summaries", response_model=list[StudentAbsenceSummary])
async def get_class_summaries(
    class_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk per-student absence counts for a class — one query for inline display."""
    _, school_id = ids
    return await att_svc.get_class_summaries(class_id, term_id, school_id, db)


@router.get("/summary", response_model=AttendanceSummaryRead)
async def get_summary(
    student_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await att_svc.get_summary(student_id, term_id, school_id, db)
