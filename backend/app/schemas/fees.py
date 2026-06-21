from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator
from app.models.fees import DiscountType, PaymentMethod


class FeeTypeCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    is_recurring: bool = True

    @field_validator("name", "code")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class FeeTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_recurring: bool | None = None
    is_active: bool | None = None


class FeeTypeRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID | None   # None = platform-wide template
    name: str
    code: str
    description: str | None
    is_recurring: bool
    is_active: bool
    model_config = {"from_attributes": True}


class FeeStructureCreate(BaseModel):
    academic_term_id: uuid.UUID
    fee_type_id: uuid.UUID
    amount: Decimal
    is_mandatory: bool = True
    applies_to_class_id: uuid.UUID | None = None
    applies_to_year_group: int | None = None
    applies_to_programme_id: uuid.UUID | None = None
    boarding_only: bool = False

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @model_validator(mode="after")
    def class_xor_cohort(self) -> "FeeStructureCreate":
        if self.applies_to_class_id and (self.applies_to_year_group or self.applies_to_programme_id):
            raise ValueError(
                "Use either applies_to_class_id OR (applies_to_year_group / applies_to_programme_id), not both."
            )
        return self


class FeeStructureUpdate(BaseModel):
    amount: Decimal | None = None
    is_mandatory: bool | None = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("amount must be positive")
        return v


class FeeStructureRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_term_id: uuid.UUID
    fee_type_id: uuid.UUID
    fee_type_name: str
    amount: Decimal
    is_mandatory: bool
    applies_to_class_id: uuid.UUID | None
    applies_to_year_group: int | None
    applies_to_programme_id: uuid.UUID | None
    boarding_only: bool


class BulkAssignResult(BaseModel):
    structure_id: uuid.UUID
    assigned: int
    skipped: int   # already had a record, not duplicated


class FeeRecordRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    fee_structure_id: uuid.UUID
    fee_type_name: str
    amount_due: Decimal
    due_date: date | None
    is_waived: bool


class FeeSummaryRead(BaseModel):
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    total_due: Decimal
    total_paid: Decimal
    total_discounted: Decimal
    balance: Decimal      # computed: total_due - total_paid - total_discounted; never stored
    last_payment_date: date | None
    updated_at: datetime

    @classmethod
    def from_model(cls, obj) -> "FeeSummaryRead":
        return cls(
            student_id=obj.student_id,
            academic_term_id=obj.academic_term_id,
            total_due=obj.total_due,
            total_paid=obj.total_paid,
            total_discounted=obj.total_discounted,
            balance=obj.total_due - obj.total_paid - obj.total_discounted,
            last_payment_date=obj.last_payment_date,
            updated_at=obj.updated_at,
        )


class FeePaymentCreate(BaseModel):
    student_id: uuid.UUID
    fee_record_id: uuid.UUID
    amount_paid: Decimal
    payment_method: PaymentMethod
    reference_number: str | None = None
    payment_date: date
    notes: str | None = None

    @field_validator("amount_paid")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount_paid must be positive")
        return v


class FeePaymentRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    fee_record_id: uuid.UUID
    amount_paid: Decimal
    payment_method: PaymentMethod
    reference_number: str | None
    received_by_id: uuid.UUID
    payment_date: date
    notes: str | None
    model_config = {"from_attributes": True}


class FeeDiscountCreate(BaseModel):
    student_id: uuid.UUID
    fee_record_id: uuid.UUID
    discount_type: DiscountType
    amount: Decimal | None = None
    percentage: Decimal | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def exactly_one_of_amount_or_percentage(self) -> "FeeDiscountCreate":
        has_amount = self.amount is not None
        has_pct = self.percentage is not None
        if has_amount == has_pct:
            raise ValueError("Provide exactly one of 'amount' or 'percentage', not both or neither.")
        if has_pct and not (Decimal("0") < self.percentage <= Decimal("100")):
            raise ValueError("percentage must be between 0 and 100 (exclusive of 0).")
        return self


class FeeDiscountRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    fee_record_id: uuid.UUID
    discount_type: DiscountType
    amount: Decimal | None
    percentage: Decimal | None
    reason: str | None
    approved_by_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class InstalmentCreate(BaseModel):
    instalment_number: int
    amount: Decimal
    due_date: date

    @field_validator("instalment_number")
    @classmethod
    def positive_num(cls, v: int) -> int:
        if v < 1:
            raise ValueError("instalment_number must be 1 or greater")
        return v

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class InstalmentRead(BaseModel):
    id: uuid.UUID
    fee_record_id: uuid.UUID
    instalment_number: int
    amount: Decimal
    due_date: date
    is_paid: bool
    model_config = {"from_attributes": True}
