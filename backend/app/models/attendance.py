"""
Group 7 — Attendance, school calendar, and schedule models.

Tables in this group:
  school_schedule      — which days of the week are school days and their hours
  ghana_public_holiday — national holidays (seeded, system-wide, no school_id)
  school_calendar      — one row per date per school; the attendance gateway
  school_period        — bell schedule (named periods within a day)
  attendance_record    — one record per student per calendar entry

ATTENDANCE GATEWAY INVARIANT
-----------------------------
AttendanceRecord.school_calendar_id is a FK to school_calendar, NOT a raw date.

This means it is architecturally impossible to:
  - Mark attendance on a day that does not exist in school_calendar
  - Mark attendance on a PUBLIC_HOLIDAY or SCHOOL_HOLIDAY day
  - Mark attendance without knowing the academic term (school_calendar links to it)

When building the "mark attendance" UI, always check that a school_calendar row
exists for the selected date AND that its day_type is SCHOOL_DAY or EXAM_DAY
before allowing teachers to submit records.
"""
from __future__ import annotations
import uuid
import enum
from datetime import date, time, datetime
from sqlalchemy import String, Boolean, Integer, Date, Time, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, SchoolScopedMixin


class DayType(str, enum.Enum):
    SCHOOL_DAY = "SCHOOL_DAY"
    PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY"
    SCHOOL_HOLIDAY = "SCHOOL_HOLIDAY"
    HALF_DAY = "HALF_DAY"
    WEEKEND = "WEEKEND"
    EXAM_DAY = "EXAM_DAY"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"


class DayOfWeek(str, enum.Enum):
    MON = "MON"
    TUE = "TUE"
    WED = "WED"
    THU = "THU"
    FRI = "FRI"
    SAT = "SAT"
    SUN = "SUN"


class SchoolSchedule(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """Defines which days of the week are school days and their hours."""
    __tablename__ = "school_schedule"
    __table_args__ = (
        UniqueConstraint("school_id", "day_of_week", name="uq_school_schedule_day"),
    )

    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek, name="dayofweek"), nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_school_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GhanaPublicHoliday(Base, UUIDPrimaryKey):
    """System-wide Ghana public holidays — no school_id."""
    __tablename__ = "ghana_public_holiday"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)


class SchoolCalendar(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    One row per school day. Gates all attendance — AttendanceRecord always
    references this table, never a raw date.
    """
    __tablename__ = "school_calendar"
    __table_args__ = (
        UniqueConstraint("school_id", "date", name="uq_school_calendar_date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    day_type: Mapped[DayType] = mapped_column(SAEnum(DayType, name="daytype"), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    academic_term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=True
    )


class SchoolPeriod(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """Bell schedule — named periods within a school day."""
    __tablename__ = "school_period"
    __table_args__ = (
        UniqueConstraint("school_id", "day_of_week", "period_number", name="uq_school_period"),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek, name="dayofweek"), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class AttendanceRecord(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    AttendanceRecord always uses school_calendar_id FK — never a raw date field.
    One record per student per calendar entry (or per period if period_id is set).
    """
    __tablename__ = "attendance_record"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "school_calendar_id", "period_id",
            name="uq_attendance_student_calendar_period"
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_calendar.id"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_period.id"), nullable=True
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendancestatus"), nullable=False
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
