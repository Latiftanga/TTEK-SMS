"""
Group 9 — Fee management: structures, payments, discounts, and summaries.

Tables in this group:
  fee_type            — categories of fees (tuition, boarding, exam levy, etc.)
  fee_structure       — the amount for a fee_type in a given term; can be filtered
                        by level or programme (e.g. boarding only for SHS students)
  student_fee_record  — what a specific student owes for a specific fee_structure
  fee_payment         — a payment made against a student_fee_record
  fee_discount        — a reduction applied to a student_fee_record (scholarship, etc.)
  fee_instalment_plan — a scheduled breakdown of a fee_record into smaller payments
  student_fee_summary — cached aggregate (total_due, total_paid, balance) per term

FEE BALANCE INVARIANT
---------------------
The fee balance (total_due - total_paid - total_discounted) is NEVER stored
as a column in the database.  It is either:

  a) Computed live:
       balance = SUM(student_fee_record.amount_due)
                 - SUM(fee_payment.amount_paid)
                 - SUM(fee_discount.amount or amount_due * percentage / 100)

  b) Read from StudentFeeSummary for performance (dashboard widgets, reports).
     StudentFeeSummary is kept in sync by a DB trigger that fires on INSERT/UPDATE
     to fee_payment and fee_discount.

If you need a student's outstanding balance, always use StudentFeeSummary
for display purposes.  Do NOT add a `balance` column to any fee table.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class DiscountType(str, enum.Enum):
    SCHOLARSHIP = "SCHOLARSHIP"
    BURSARY = "BURSARY"
    SIBLING = "SIBLING"
    STAFF_WARD = "STAFF_WARD"
    EXEMPTION = "EXEMPTION"
    OTHER = "OTHER"


class FeeType(Base, UUIDPrimaryKey, TimestampMixin):
    """Fee category definition (e.g. Tuition, Boarding, Exam Levy). school_id=NULL means platform-wide template."""
    __tablename__ = "fee_type"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    structures: Mapped[list[FeeStructure]] = relationship(back_populates="fee_type")


class FeeStructure(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """The amount charged for a fee type in a specific term, optionally scoped to a level or programme."""
    __tablename__ = "fee_structure"

    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fee_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_type.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Scope — mutually exclusive: class_id OR (year_group + programme_id), never both.
    # NULL on all three means the fee applies to every enrolled student.
    applies_to_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id", ondelete="SET NULL"), nullable=True
    )
    applies_to_year_group: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applies_to_programme_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shs_programme.id"), nullable=True
    )
    boarding_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fee_type: Mapped[FeeType] = relationship(back_populates="structures")
    student_records: Mapped[list[StudentFeeRecord]] = relationship(back_populates="fee_structure")


class StudentFeeRecord(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """One ledger entry per student per fee structure — records the amount owed."""
    __tablename__ = "student_fee_record"
    __table_args__ = (
        UniqueConstraint("student_id", "fee_structure_id", name="uq_student_fee_record"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False, index=True
    )
    fee_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_structure.id"), nullable=False, index=True
    )
    amount_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_waived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fee_structure: Mapped[FeeStructure] = relationship(back_populates="student_records")
    payments: Mapped[list[FeePayment]] = relationship(back_populates="fee_record")
    discounts: Mapped[list[FeeDiscount]] = relationship(back_populates="fee_record")
    instalment_plans: Mapped[list[FeeInstalmentPlan]] = relationship(back_populates="fee_record")


class FeePayment(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """A single payment credited against a StudentFeeRecord."""
    __tablename__ = "fee_payment"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False, index=True
    )
    fee_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fee_record.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="paymentmethod"), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    fee_record: Mapped[StudentFeeRecord] = relationship(back_populates="payments")


class FeeDiscount(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """
    A discount applied to a StudentFeeRecord (scholarship, bursary, sibling reduction, etc.).

    INVARIANT: exactly one of `amount` (fixed GHS reduction) or `percentage` (0-100) must
    be set — never both, never neither.  Enforced by a DB check constraint.
    The service layer is responsible for computing the effective reduction before
    updating StudentFeeSummary.
    """
    __tablename__ = "fee_discount"
    __table_args__ = (
        CheckConstraint(
            "(amount IS NOT NULL AND percentage IS NULL)"
            " OR (amount IS NULL AND percentage IS NOT NULL)",
            name="ck_fee_discount_exactly_one_of_amount_or_percentage",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False, index=True
    )
    fee_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fee_record.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discount_type: Mapped[DiscountType] = mapped_column(SAEnum(DiscountType, name="discounttype"), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    fee_record: Mapped[StudentFeeRecord] = relationship(back_populates="discounts")


class FeeInstalmentPlan(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """A scheduled instalment within a fee record's payment plan."""
    __tablename__ = "fee_instalment_plan"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fee_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fee_record.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instalment_number: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fee_record: Mapped[StudentFeeRecord] = relationship(back_populates="instalment_plans")


class StudentFeeSummary(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Cached fee aggregate per student per term — maintained by a DB trigger.

    Updated automatically on INSERT/UPDATE to fee_payment and fee_discount.
    Always prefer reading from here for dashboards and reports rather than
    summing raw payment rows.  Never write to this table from application code.

    Do NOT add a `balance` column — balance = total_due - total_paid - total_discounted.
    """
    __tablename__ = "student_fee_summary"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_term_id", name="uq_fee_summary"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False
    )
    total_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_discounted: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    last_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
