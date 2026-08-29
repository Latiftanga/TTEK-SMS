"""
Guardian/student-submitted absence excuse requests — a self-service
counterpart to the after-the-fact absence SMS: a guardian can explain an
absence in advance (or after) instead of only ever being notified once it's
already happened. Closest existing precedent is StaffLeave (self-service
submit, list-pending, terminal-status-only review) — see services/
staff_leave.py — with the addition of tracking WHO submitted it (a guardian
acting for one of possibly several children, unlike staff leave's implicit
self-reference).

On APPROVED, services/attendance_excuse.py::review_excuse_request() marks
every markable calendar day in [start_date, end_date] EXCUSED for the
student — see that module for the exact term-lock/current-term rules.
"""
from __future__ import annotations
import uuid
import enum
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, SchoolScopedMixin


class ExcuseStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AbsenceExcuseRequest(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "absence_excuse_request"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_excuse_request_date_order"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Set when a guardian submits on behalf of a linked child; NULL when the
    # student submitted for themselves (portal ADMISSION_ID login).
    guardian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guardian.id"), nullable=True
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ExcuseStatus] = mapped_column(
        SAEnum(ExcuseStatus, name="excusestatus"), default=ExcuseStatus.PENDING, nullable=False
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
