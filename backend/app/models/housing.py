"""
Group 6 — Boarding house, room assignment, night roll call, and exeat models.

Tables in this group:
  house                   — a boarding house (male, female, or mixed)
  house_master            — staff assigned as housemaster per academic year
  room                    — individual rooms within a house
  student_house_assignment — which student is in which house/room per year
  night_roll_call         — headcount recorded by housemaster each night
  exeat                   — formal permission for a student to leave campus

NIGHT ROLL CALL NOTE
--------------------
NightRollCall.school_calendar_id is a FK to school_calendar, NOT a raw date.
This mirrors the attendance invariant (see models/attendance.py) — it prevents
roll calls from being created on days when the school is officially closed.

EXEAT NOTE
----------
An Exeat is a request workflow: student (or guardian) requests → admin approves.
The actual return date is captured in actual_return_date (nullable) when the
student comes back, which may differ from the planned return_date.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class HouseGender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    MIXED = "MIXED"


class ExeatStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"


class ExeatType(str, enum.Enum):
    INTERNAL = "INTERNAL"  # student leaves house but stays on school grounds
    EXTERNAL = "EXTERNAL"  # student leaves school premises entirely


class House(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """A boarding house within the school. Gender determines which students can be assigned."""
    __tablename__ = "house"
    __table_args__ = (
        UniqueConstraint("school_id", "code", name="uq_house_school_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    gender: Mapped[HouseGender] = mapped_column(SAEnum(HouseGender, name="housegender"), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rooms: Mapped[list[Room]] = relationship(back_populates="house", cascade="all, delete-orphan")
    house_masters: Mapped[list[HouseMaster]] = relationship(back_populates="house")
    student_assignments: Mapped[list[StudentHouseAssignment]] = relationship(back_populates="house")


class HouseMaster(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """The staff member responsible for a house in a given academic year."""
    __tablename__ = "house_master"

    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("house.id", ondelete="CASCADE"), nullable=False, index=True
    )
    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_year.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    house: Mapped[House] = relationship(back_populates="house_masters")


class Room(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    A physical room within a boarding house.

    room_type is a free-form string; the expected values are:
    DORMITORY, SICK_BAY, PREFECT, STAFF.  Defaults to DORMITORY.
    """
    __tablename__ = "room"

    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("house.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room_type: Mapped[str] = mapped_column(String(50), default="DORMITORY", nullable=False)

    house: Mapped[House] = relationship(back_populates="rooms")
    student_assignments: Mapped[list[StudentHouseAssignment]] = relationship(back_populates="room")


class StudentHouseAssignment(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Links a student to a house (and optionally a room) for an academic year.

    INVARIANT: vacated_at must be NULL (still resident) or >= assigned_at.
    Enforced by a DB check constraint.
    """
    __tablename__ = "student_house_assignment"
    __table_args__ = (
        CheckConstraint(
            "vacated_at IS NULL OR vacated_at >= assigned_at",
            name="ck_house_assignment_vacated_after_assigned",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("house.id"), nullable=False
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room.id"), nullable=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_year.id"), nullable=False
    )
    assigned_at: Mapped[date] = mapped_column(Date, nullable=False)
    vacated_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    house: Mapped[House] = relationship(back_populates="student_assignments")
    room: Mapped[Room | None] = relationship(back_populates="student_assignments")


class NightRollCall(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Nightly headcount recorded by the housemaster.

    Uses school_calendar_id (not a raw date) so roll calls cannot be created
    on days when the school calendar marks the school as closed.
    """
    __tablename__ = "night_roll_call"

    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("house.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_calendar.id"), nullable=False, index=True
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    total_present: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Exeat(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """
    Formal permission for a student to leave campus temporarily.

    Lifecycle: PENDING → APPROVED or REJECTED → RETURNED (when student comes back).
    actual_return_date is set on return and may differ from the planned return_date.

    INVARIANT: return_date >= departure_date (enforced by DB check constraint).
    """
    __tablename__ = "exeat"
    __table_args__ = (
        CheckConstraint("return_date >= departure_date", name="ck_exeat_return_after_departure"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    exeat_type: Mapped[ExeatType] = mapped_column(
        SAEnum(ExeatType, name="exeattype"), default=ExeatType.EXTERNAL, nullable=False
    )
    status: Mapped[ExeatStatus] = mapped_column(
        SAEnum(ExeatStatus, name="exeatstatus"), default=ExeatStatus.PENDING, nullable=False
    )
    actual_return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
