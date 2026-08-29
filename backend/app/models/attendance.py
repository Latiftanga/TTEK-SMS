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
    """Defines which days of the week are school days — read by
    generate_calendar() (services/attendance_calendar.py) to decide
    SCHOOL_DAY vs WEEKEND. Deliberately does NOT carry a start/end time for
    the day: SchoolPeriod (this same module) is the sole source of a day's
    time structure now, with real per-period granularity instead of one
    start/end pair for the whole day — a school that never adopts
    period-level timetabling still only needs this open/closed flag."""
    __tablename__ = "school_schedule"
    __table_args__ = (
        UniqueConstraint("school_id", "day_of_week", name="uq_school_schedule_day"),
    )

    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek, name="dayofweek"), nullable=False)
    is_school_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GhanaPublicHoliday(Base, UUIDPrimaryKey):
    """
    System-wide Ghana public holidays — no school_id. Managed exclusively by
    superadmin (services/attendance_holidays.py), since this is shared
    reference data every school's calendar generation reads from.

    is_recurring=True  → a fixed-date holiday (Independence Day, Labour Day,
                          Christmas, ...) — generate_calendar() matches it by
                          (month, day) every year, not just the year it was
                          originally seeded for.
    is_recurring=False → a moveable-date holiday (Easter/Good Friday, Eid
                          ul-Fitr, Eid ul-Adha) whose date shifts every year —
                          matched by exact date only, so a new row must be
                          added for each year it applies.
    """
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
    # Set by override_calendar_day() — protects this day's day_type from being
    # silently recomputed/overwritten by generate_calendar(force=True).
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SchoolPeriod(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """Bell schedule — named periods within a school day. Within the same
    school+day, name/start_time/end_time are each independently unique (not
    just period_number) — two periods can't share a label or a start/end
    clock time on the same day, which would either be a duplicate entry or
    two periods double-booked at the same instant. The same name/start/end
    repeating on a DIFFERENT day is completely normal (e.g. an identical
    Monday/Tuesday bell schedule via copy_periods_to_days), so these
    constraints are scoped per day_of_week, not school-wide."""
    __tablename__ = "school_period"
    __table_args__ = (
        UniqueConstraint("school_id", "day_of_week", "period_number", name="uq_school_period"),
        UniqueConstraint("school_id", "day_of_week", "name", name="uq_school_period_name"),
        UniqueConstraint("school_id", "day_of_week", "start_time", name="uq_school_period_start"),
        UniqueConstraint("school_id", "day_of_week", "end_time", name="uq_school_period_end"),
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


class CalendarOverrideLog(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Audit trail for override_calendar_day() — every manual day_type change is
    recorded here, since SchoolCalendar itself only ever holds the current
    state (is_manual_override is a boolean flag, not a history).

    calendar_id is SET NULL (not CASCADE) so the log survives the calendar
    row it documents, matching AttendanceAuditLog's own convention.
    """
    __tablename__ = "calendar_override_log"

    calendar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_calendar.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    old_day_type: Mapped[DayType] = mapped_column(SAEnum(DayType, name="daytype"), nullable=False)
    new_day_type: Mapped[DayType] = mapped_column(SAEnum(DayType, name="daytype"), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AttendanceAuditLog(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Immutable log of an attendance submission made against a locked term
    (AcademicTerm.results_locked) — mirrors BehaviourAuditLog/AssessmentAuditLog's
    same override-audit shape. Only written when check_term_lock_override()
    actually resolves an override reason (i.e. the term was locked); an
    ordinary submission against an unlocked term writes no row here.

    attendance_record_id is SET NULL (not CASCADE) on delete so the log
    survives the record it documents.
    """
    __tablename__ = "attendance_audit_log"

    attendance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attendance_record.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id"), nullable=False
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendancestatus"), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AttendanceRiskTier(str, enum.Enum):
    """Chronic-absenteeism early-warning tiers — see services/attendance_risk.py
    for the exact thresholds and the research they're based on."""
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    SEVERE = "SEVERE"


class AttendanceRiskAlert(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Tracks the HIGHEST AttendanceRiskTier a student has already been alerted
    for, per term — so crossing into AT_RISK once doesn't re-fire a guardian
    SMS on every subsequent absence within that same tier. A tier increase
    (e.g. AT_RISK → SEVERE) fires again and bumps this row; it is never
    lowered by a later PRESENT mark within the same term (the alert already
    sent is a fact, not a live gauge).
    """
    __tablename__ = "attendance_risk_alert"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_term_id", name="uq_attendance_risk_alert"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False
    )
    tier: Mapped[AttendanceRiskTier] = mapped_column(
        SAEnum(AttendanceRiskTier, name="attendancerisktier"), nullable=False
    )
    alerted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
