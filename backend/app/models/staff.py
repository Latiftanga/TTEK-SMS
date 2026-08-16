"""
Group 3 — Staff member profiles.

Tables in this group:
  staff_category           — HR employment classification (Teaching, Catering, Security, etc.)
  staff_rank               — named rank within a category (e.g. "Principal Superintendent I")
  staff_member             — the employment record for a teacher or admin
  staff_emergency_contact  — next-of-kin contact details

Career history — staff_promotion, staff_qualification, staff_leave — lives in
models/staff_history.py, split out to stay under the 300-line cap. Their
relationships back to StaffMember use quoted string targets rather than a
Python import, to avoid a circular import between the two files (matching
this file's own existing StaffMember.positions → StaffPosition pattern,
which crosses into models/auth.py the same way).

RELATIONSHIP TO USER
--------------------
A StaffMember record is the professional profile.
A User record (Group 2 — models/auth.py) is the login identity.
They are linked via User.staff_member_id → StaffMember.id.

CATEGORY vs RANK vs POSITION
-----------------------------
StaffCategory = what someone is employed to do (Teaching, Catering, Security…).
               Has staff_type (TEACHING | NON_TEACHING) for filtering.
               Pure HR — no system permissions. GES templates have school_id=NULL.

StaffRank     = named rank within a category (e.g. "Assistant Director II Basic Grade").
               Used in promotion history for consistency — prevents free-text spelling
               variants. GES templates have school_id=NULL. Private schools create
               their own (school_id=set) or use none at all.

StaffPosition = an authority role assigned on top of employment (HEAD, HOD,
               CLASS_TEACHER, HOUSEMASTER…). Comes with system permissions.
               Many-to-many: one person can hold several simultaneously.

CURRENT RANK
------------
A staff member's current rank is NOT stored as a field — it is always derived
as the to_rank of their most recent StaffPromotion (ordered by effective_date DESC).
This avoids redundant storage and the sync bugs that come with it.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import (
    Boolean, Column, Date, ForeignKey,
    String, Table, Text, UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey

# Many-to-many: a staff member can hold multiple positions simultaneously.
staff_member_positions = Table(
    "staff_member_positions",
    Base.metadata,
    Column("staff_member_id", UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), primary_key=True),
    Column("position_id", UUID(as_uuid=True), ForeignKey("staff_position.id", ondelete="CASCADE"), primary_key=True),
)


class StaffType(str, enum.Enum):
    TEACHING = "TEACHING"
    NON_TEACHING = "NON_TEACHING"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class EmploymentType(str, enum.Enum):
    PERMANENT = "PERMANENT"
    CONTRACT = "CONTRACT"
    NATIONAL_SERVICE = "NATIONAL_SERVICE"
    INTERN = "INTERN"


class MaritalStatus(str, enum.Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    SEPARATED = "SEPARATED"


class StaffCategory(Base, UUIDPrimaryKey, TimestampMixin):
    """
    HR employment classification — what a person is employed to do.

    GES template categories (is_template=True, school_id=NULL) are seeded at
    startup and shared across all schools: Teaching, Accounting, Catering, etc.

    Each school may also create custom categories (school_id set, is_template=False)
    for job families not covered by GES (e.g. "IT Support" in a private school).

    staff_type drives the TEACHING/NON_TEACHING split:
    - TEACHING   → shown in class teacher / subject teacher assignment dropdowns;
                   also auto-derives the TEACHER StaffPosition (see
                   core/permissions.py::resolve_permissions) — being a teacher is
                   the core role, not an optional responsibility a staff member is
                   manually granted, unlike Class Teacher/Housemaster/Headmaster.
    - NON_TEACHING → excluded from those dropdowns, no derived position

    All OTHER permissions still come from StaffPosition (authority roles),
    not from employment classification — TEACHER is the one deliberate
    exception, not a general rule that categories grant access.
    """
    __tablename__ = "staff_category"
    __table_args__ = (
        UniqueConstraint("school_id", "code", name="uq_staff_category_school_code"),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    staff_type: Mapped[StaffType | None] = mapped_column(
        SAEnum(StaffType, name="stafftype"), nullable=True
    )
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ranks: Mapped[list[StaffRank]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class StaffRank(Base, UUIDPrimaryKey, TimestampMixin):
    """
    A named rank within a StaffCategory.

    GES template ranks (school_id=NULL, is_template=True) are seeded for all
    23 GES job classes. Public schools see these in promotion dropdowns.
    Private schools see only their own custom ranks (school_id=set).

    Using FK references instead of free-text ensures "Asst. Director II" cannot
    be entered as "Assistant Director 2" by different users — consistency matters
    when exporting staff registers to GES or CAGD.
    """
    __tablename__ = "staff_rank"
    __table_args__ = (
        UniqueConstraint("school_id", "category_id", "title", name="uq_staff_rank_school_cat_title"),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_category.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped[StaffCategory] = relationship(back_populates="ranks")


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
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_category.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, name="gender"), nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        SAEnum(EmploymentType, name="employmenttype"), nullable=True
    )
    marital_status: Mapped[MaritalStatus | None] = mapped_column(
        SAEnum(MaritalStatus, name="maritalstatus"), nullable=True
    )
    ssnit_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    category: Mapped[StaffCategory | None] = relationship("StaffCategory", lazy="selectin")
    positions: Mapped[list["StaffPosition"]] = relationship(  # type: ignore[name-defined]
        "StaffPosition", secondary=staff_member_positions, lazy="selectin"
    )
    emergency_contacts: Mapped[list[StaffEmergencyContact]] = relationship(
        back_populates="staff_member", cascade="all, delete-orphan"
    )
    promotions: Mapped[list["StaffPromotion"]] = relationship(  # type: ignore[name-defined]
        "StaffPromotion", back_populates="staff_member", cascade="all, delete-orphan"
    )
    qualifications: Mapped[list["StaffQualification"]] = relationship(  # type: ignore[name-defined]
        "StaffQualification", back_populates="staff_member", cascade="all, delete-orphan"
    )
    leaves: Mapped[list["StaffLeave"]] = relationship(  # type: ignore[name-defined]
        "StaffLeave", back_populates="staff_member", cascade="all, delete-orphan"
    )


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
