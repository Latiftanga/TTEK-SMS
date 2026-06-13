"""
Group 3 — Staff member profiles, qualifications, promotions, and leave.

Tables in this group:
  staff_member             — the employment record for a teacher or admin
  staff_emergency_contact  — next-of-kin contact details
  staff_promotion          — history of position changes
  staff_qualification      — academic and professional certificates
  staff_leave              — leave applications and their approval status

RELATIONSHIP TO USER
--------------------
A StaffMember record is the professional profile.
A User record (Group 2 — models/auth.py) is the login identity.
They are linked via User.staff_member_id → StaffMember.id.

A staff member exists before their login account is created (e.g. the headmaster
creates the StaffMember record, then sends an invitation to the staff member's
email so they can create their own password via the accept-invite flow).
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class StaffMember(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """
    The employment record for a teacher or administrative staff member.

    This is the professional profile — see models/auth.py User for the login
    identity.  A StaffMember can exist without a User account (e.g. before the
    invitation is accepted), but a staff User always links back here.
    """
    __tablename__ = "staff_member"
    __table_args__ = (
        UniqueConstraint("school_id", "staff_number", name="uq_staff_member_school_number"),
    )

    staff_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, name="gender"), nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_position.id"), nullable=True
    )
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    emergency_contacts: Mapped[list[StaffEmergencyContact]] = relationship(
        back_populates="staff_member", cascade="all, delete-orphan"
    )
    promotions: Mapped[list[StaffPromotion]] = relationship(back_populates="staff_member")
    qualifications: Mapped[list[StaffQualification]] = relationship(
        back_populates="staff_member", cascade="all, delete-orphan"
    )
    leaves: Mapped[list[StaffLeave]] = relationship(back_populates="staff_member")


class StaffEmergencyContact(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """Next-of-kin or emergency contact for a staff member."""
    __tablename__ = "staff_emergency_contact"

    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    staff_member: Mapped[StaffMember] = relationship(back_populates="emergency_contacts")


class StaffPromotion(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """A single position change event in a staff member's career history."""
    __tablename__ = "staff_promotion"

    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_position.id"), nullable=True
    )
    to_position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_position.id"), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    staff_member: Mapped[StaffMember] = relationship(back_populates="promotions")


class StaffQualification(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    An academic or professional certificate held by a staff member.

    year_obtained=NULL means the year is unknown or not yet recorded —
    it does NOT indicate a pending or incomplete qualification.
    """
    __tablename__ = "staff_qualification"

    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    qualification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(200), nullable=True)
    year_obtained: Mapped[int | None] = mapped_column(nullable=True)
    certificate_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    staff_member: Mapped[StaffMember] = relationship(back_populates="qualifications")


class StaffLeave(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """
    A leave application submitted by a staff member.

    INVARIANT: start_date must be on or before end_date (enforced by DB constraint).
    days_count is stored explicitly because the school calendar may exclude weekends
    and public holidays from the count — callers must compute and supply it.
    """
    __tablename__ = "staff_leave"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_staff_leave_dates"),
    )

    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(
        SAEnum(LeaveStatus, name="leavestatus"), default=LeaveStatus.PENDING, nullable=False
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    staff_member: Mapped[StaffMember] = relationship(back_populates="leaves")
