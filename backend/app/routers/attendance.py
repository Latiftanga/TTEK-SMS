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
from app.core.dependencies import require_permission
from app.schemas.academic import ClassRead
from app.schemas.attendance import (
    AttendanceMarkRequest, AttendanceRecordRead, AttendanceSummaryRead,
    CalendarDayOverride, CalendarDayRead, CalendarGenerateRequest, CalendarRangeOverride,
    ClassMarkingStatusRead, MarkablePeriod, PeriodMarkingStatusRead, ScheduleRead, ScheduleUpsert,
    StudentAbsenceSummary, TodayStatusRead,
)
from app.schemas.attendance_excuse import ExcuseRequestRead, ExcuseRequestReview
from app.schemas.attendance_risk import AtRiskStudentRead
from app.services import attendance as att_svc
from app.services import attendance_calendar as cal_svc
from app.services import attendance_excuse as excuse_svc
from app.services import attendance_period_status as period_status_svc
from app.services import attendance_periods as period_svc
from app.services import attendance_risk as risk_svc
from app.services import attendance_summary as att_summary_svc

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
    ids=Depends(require_permission("attendance", "view")),
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
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return [CalendarDayRead.model_validate(d) for d in await cal_svc.list_calendar(school_id, term_id, db)]


@router.patch("/calendar/range", response_model=list[CalendarDayRead])
async def override_calendar_range(
    req: CalendarRangeOverride,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    """Mark every generated calendar day in a date range at once — e.g. a
    week-long mid-term break — instead of one PATCH /calendar/{cal_id} call
    per day. Registered before /calendar/{cal_id} so "range" is never
    swallowed by that route's path parameter."""
    user_id, school_id = ids
    days = await cal_svc.override_calendar_range(req, school_id, user_id, db)
    return [CalendarDayRead.model_validate(d) for d in days]


@router.patch("/calendar/{cal_id}", response_model=CalendarDayRead)
async def override_calendar_day(
    cal_id: uuid.UUID,
    req: CalendarDayOverride,
    ids=Depends(require_permission("attendance", "approve")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return CalendarDayRead.model_validate(
        await cal_svc.override_calendar_day(cal_id, req, school_id, user_id, db)
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
    period_id: uuid.UUID | None = Query(None),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await att_svc.list_attendance(calendar_id, class_id, school_id, user_id, db, period_id=period_id)


@router.get("/markable-periods", response_model=list[MarkablePeriod])
async def list_markable_periods(
    class_id: uuid.UUID = Query(...),
    calendar_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Periods the caller can mark attendance for on this class+day —
    additive to the always-available whole-day roll call. Returns [] when
    the school hasn't opted into period-level attendance."""
    user_id, school_id = ids
    return await period_svc.list_markable_periods(class_id, calendar_id, school_id, user_id, db)


@router.get("/today", response_model=TodayStatusRead)
async def get_today_status(
    class_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Today's calendar status + existing record count for a class — single fast call."""
    user_id, school_id = ids
    return await att_summary_svc.get_today_status(class_id, school_id, user_id, db)


@router.get("/class-summaries", response_model=list[StudentAbsenceSummary])
async def get_class_summaries(
    class_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk per-student absence counts for a class — one query for inline display."""
    user_id, school_id = ids
    return await att_summary_svc.get_class_summaries(class_id, term_id, school_id, user_id, db)


@router.get("/summary", response_model=AttendanceSummaryRead)
async def get_summary(
    student_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await att_summary_svc.get_summary(student_id, term_id, school_id, user_id, db)


@router.get("/marking-status", response_model=list[ClassMarkingStatusRead])
async def get_marking_status(
    calendar_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Every visible class' marking status for one calendar day — the
    "who's marked, who hasn't" oversight view."""
    user_id, school_id = ids
    return await att_summary_svc.get_marking_status(calendar_id, school_id, user_id, db)


@router.get("/period-marking-status", response_model=list[PeriodMarkingStatusRead])
async def get_period_marking_status(
    calendar_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Period-level sibling of /marking-status — every visible (class,
    period) pair that's actually timetabled, with its marked status. []
    when the school hasn't opted into period-level attendance."""
    user_id, school_id = ids
    return await period_status_svc.get_period_marking_status(calendar_id, school_id, user_id, db)


@router.get("/at-risk", response_model=list[AtRiskStudentRead])
async def get_at_risk_students(
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Chronic-absenteeism early-warning list — every visible student whose
    term-to-date attendance has crossed a risk tier (see attendance_risk.py)."""
    user_id, school_id = ids
    return await risk_svc.list_at_risk(term_id, school_id, user_id, db)


@router.get("/excuse-requests", response_model=list[ExcuseRequestRead])
async def list_pending_excuse_requests(
    ids=Depends(require_permission("attendance", "record")),
    db: AsyncSession = Depends(get_db),
):
    """Every visible PENDING guardian/student excuse request — scoped like
    every other attendance read (unrestricted for attendance.approve, else
    the caller's own ClassTeacher classes this year)."""
    user_id, school_id = ids
    return await excuse_svc.list_pending_excuse_requests(school_id, user_id, db)


@router.patch("/excuse-requests/{request_id}/review", response_model=ExcuseRequestRead)
async def review_excuse_request(
    request_id: uuid.UUID,
    req: ExcuseRequestReview,
    ids=Depends(require_permission("attendance", "record")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await excuse_svc.review_excuse_request(request_id, req, school_id, user_id, db)


@router.get("/my-classes", response_model=list[ClassRead])
async def list_my_classes(
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Classes the caller can mark attendance for — scoped to their own
    ClassTeacher assignment(s) unless they hold attendance.approve."""
    user_id, school_id = ids
    return await att_summary_svc.list_my_classes(term_id, school_id, user_id, db)
