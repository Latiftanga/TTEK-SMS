from __future__ import annotations
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from app.models.attendance import AttendanceStatus, DayOfWeek, DayType


class ScheduleUpsert(BaseModel):
    day_of_week: DayOfWeek
    is_school_day: bool = True


class ScheduleRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    day_of_week: DayOfWeek
    is_school_day: bool
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


class CalendarRangeOverride(BaseModel):
    """Mark every generated calendar day in [start_date, end_date] with the
    same day_type/notes in one call — e.g. a week-long mid-term break,
    rather than one override_calendar_day() call per day."""
    start_date: date
    end_date: date
    day_type: DayType
    notes: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _valid_range(self) -> "CalendarRangeOverride":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 180:
            raise ValueError("Range too large — must be 180 days or fewer.")
        return self


class AttendanceMark(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus
    notes: str | None = None


class AttendanceMarkRequest(BaseModel):
    school_calendar_id: uuid.UUID
    class_id: uuid.UUID
    records: list[AttendanceMark]
    override_reason: str | None = None
    # None = the default whole-day roll call. A real SchoolPeriod id marks
    # that one period instead — additive, never replaces the whole-day
    # record — only accepted when School.has_period_attendance is true.
    period_id: uuid.UUID | None = None


class AttendanceRecordRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    school_calendar_id: uuid.UUID
    class_id: uuid.UUID
    period_id: uuid.UUID | None
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


class ClassMarkingStatusRead(BaseModel):
    class_id: uuid.UUID
    name: str
    student_count: int
    present: int
    absent: int
    marked: bool
    class_teacher_name: str | None


# ── Bell periods (SchoolPeriod) ──────────────────────────────────────────────

class PeriodCreate(BaseModel):
    name: str = Field(max_length=50)
    day_of_week: DayOfWeek
    period_number: int
    start_time: time
    end_time: time


class PeriodUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    start_time: time | None = None
    end_time: time | None = None


class PeriodRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    day_of_week: DayOfWeek
    period_number: int
    start_time: time
    end_time: time
    model_config = {"from_attributes": True}


class PeriodCopyRequest(BaseModel):
    """Clone every period on source_day onto each of target_days — the
    realistic setup path for a school whose bell times repeat Mon–Fri,
    avoiding a hand-entry of the same periods five times over."""
    source_day: DayOfWeek
    target_days: list[DayOfWeek]


class MarkablePeriod(BaseModel):
    """One row of the period picker on the Mark Attendance page — see
    services/attendance_periods.py::list_markable_periods()."""
    period_id: uuid.UUID
    name: str
    start_time: time
    end_time: time
    subject_id: uuid.UUID
    subject_name: str
    teacher_name: str | None
    can_mark: bool
    already_marked: bool
