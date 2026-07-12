from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class PortalProfile(BaseModel):
    student_id: uuid.UUID
    admission_number: str
    display_name: str
    current_class_name: str | None
    school_name: str


class PortalTermEnrollmentRead(BaseModel):
    id: uuid.UUID
    academic_term_id: uuid.UUID
    term_name: str
    academic_year_name: str
    is_current: bool
    is_published: bool
    # None = no fees assigned for this term yet, not a zero balance.
    # fee_balance is computed live (total_due - total_paid - total_discounted),
    # never stored — same rule as StudentFeeSummary everywhere else.
    fee_total_due: Decimal | None = None
    fee_total_paid: Decimal | None = None
    fee_balance: Decimal | None = None
    fee_last_payment_date: date | None = None
