from __future__ import annotations
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceStatus, DayOfWeek, DayType


class ScheduleUpsert(BaseModel):
    day_of_week: DayOfWeek
    is_school_day: bool = True
    start_time: time | None = None
    end_time: time | None = None


class ScheduleRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    day_of_week: DayOfWeek
    is_school_day: bool
    start_time: time | None
    end_time: time | None
    model_config = {"from_attributes": True}


class CalendarGenerateRequest(BaseModel):
    term_id: uuid.UUID
    force: bool = False  # when True, re-evaluates existing entries against current schedule


class CalendarDayRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    date: date
    day_type: DayType
    notes: str | None
    academic_term_id: uuid.UUID | None
    is_manual_override: bool
    model_config = {"from_attributes": True}


class CalendarDayOverride(BaseModel):
    day_type: DayType
    notes: str | None = Field(default=None, max_length=300)


class AttendanceMark(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus
    notes: str | None = None


class AttendanceMarkRequest(BaseModel):
    school_calendar_id: uuid.UUID
    class_id: uuid.UUID
    records: list[AttendanceMark]
    override_reason: str | None = None


class AttendanceRecordRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    school_calendar_id: uuid.UUID
    class_id: uuid.UUID
    status: AttendanceStatus
    notes: str | None
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    model_config = {"from_attributes": True}


class AttendanceSummaryRead(BaseModel):
    student_id: uuid.UUID
    term_id: uuid.UUID
    total_school_days: int
    days_present: int
    days_absent: int
    days_late: int
    days_excused: int
    days_unmarked: int = 0
    attendance_rate: float  # 0.0–100.0


class TodayStatusRead(BaseModel):
    calendar_day: CalendarDayRead | None
    is_markable: bool
    record_count: int


class StudentAbsenceSummary(BaseModel):
    student_id: uuid.UUID
    days_absent: int
    days_late: int
    attendance_rate: float  # 0.0–100.0
