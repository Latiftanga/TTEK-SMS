"""
Staff career history — promotions, qualifications, and leave. Split out of
models/staff.py to stay under the 300-line cap.

Cross-file relationships to StaffMember/StaffRank (both in models/staff.py)
use quoted string targets, matching the existing StaffMember.positions →
StaffPosition (models/auth.py) pattern already in this codebase — this
avoids a circular import between the two files. Both modules must be
imported somewhere before SQLAlchemy configures its mappers (see the
"import all models" list in alembic/env.py, conftest.py, and the seed
scripts) for the string references to resolve.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, Date, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class StaffPromotion(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    A career rank change event in a staff member's history.

    from_rank_id is null for the very first recorded promotion.
    to_rank_id is a FK to StaffRank — this enforces consistent rank titles
    across all users and makes GES/CAGD exports reliable.

    Current rank is derived at query time as the to_rank of the most recent
    promotion (ordered by effective_date DESC) — it is never stored redundantly.
    """
    __tablename__ = "staff_promotion"

    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_rank_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_rank.id", ondelete="SET NULL"), nullable=True
    )
    to_rank_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_rank.id", ondelete="SET NULL"), nullable=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    staff_member: Mapped["StaffMember"] = relationship(  # type: ignore[name-defined]
        "StaffMember", back_populates="promotions"
    )
    from_rank: Mapped["StaffRank | None"] = relationship(  # type: ignore[name-defined]
        "StaffRank", foreign_keys=[from_rank_id], lazy="selectin"
    )
    to_rank: Mapped["StaffRank | None"] = relationship(  # type: ignore[name-defined]
        "StaffRank", foreign_keys=[to_rank_id], lazy="selectin"
    )


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

    staff_member: Mapped["StaffMember"] = relationship(  # type: ignore[name-defined]
        "StaffMember", back_populates="qualifications"
    )


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

    staff_member: Mapped["StaffMember"] = relationship(  # type: ignore[name-defined]
        "StaffMember", back_populates="leaves"
    )
