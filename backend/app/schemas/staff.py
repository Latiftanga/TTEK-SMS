from __future__ import annotations
import uuid
from datetime import date, datetime
from pydantic import BaseModel, field_validator
from app.models.staff import Gender, LeaveStatus


class StaffMemberCreate(BaseModel):
    staff_number: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    date_of_birth: date | None = None
    gender: Gender | None = None
    national_id: str | None = None
    phone: str | None = None
    email: str | None = None
    position_id: uuid.UUID | None = None
    department: str | None = None
    joined_date: date | None = None

    @field_validator("staff_number", "first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class StaffMemberUpdate(BaseModel):
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    national_id: str | None = None
    phone: str | None = None
    email: str | None = None
    position_id: uuid.UUID | None = None
    department: str | None = None
    is_active: bool | None = None
    joined_date: date | None = None


class StaffMemberSummary(BaseModel):
    """Flat view used in list responses — no nested collections."""
    id: uuid.UUID
    school_id: uuid.UUID
    staff_number: str
    first_name: str
    middle_name: str | None
    last_name: str
    display_name: str
    gender: Gender | None
    phone: str | None
    email: str | None
    position_id: uuid.UUID | None
    position_name: str | None    # denormalized via JOIN
    department: str | None
    is_active: bool
    joined_date: date | None


class StaffMemberDetail(StaffMemberSummary):
    """Full profile view — includes nested sub-records."""
    date_of_birth: date | None
    national_id: str | None
    photo_path: str | None
    qualifications: list[QualificationRead] = []
    emergency_contacts: list[EmergencyContactRead] = []


class EmergencyContactCreate(BaseModel):
    name: str
    contact_type: str    # "Spouse", "Parent", "Sibling", etc.
    phone: str
    email: str | None = None


class EmergencyContactRead(BaseModel):
    id: uuid.UUID
    name: str
    contact_type: str
    phone: str
    email: str | None

    model_config = {"from_attributes": True}


class QualificationCreate(BaseModel):
    institution: str
    qualification_type: str    # "Bachelor's", "Master's", "PGCE", etc.
    field_of_study: str | None = None
    year_obtained: int | None = None


class QualificationRead(BaseModel):
    id: uuid.UUID
    institution: str
    qualification_type: str
    field_of_study: str | None
    year_obtained: int | None

    model_config = {"from_attributes": True}


class PromotionCreate(BaseModel):
    from_position_id: uuid.UUID | None = None
    to_position_id: uuid.UUID
    effective_date: date
    reason: str | None = None


class PromotionRead(BaseModel):
    id: uuid.UUID
    staff_member_id: uuid.UUID
    from_position_id: uuid.UUID | None
    from_position_name: str | None
    to_position_id: uuid.UUID
    to_position_name: str
    effective_date: date
    reason: str | None
    created_at: datetime


class LeaveCreate(BaseModel):
    leave_type: str    # "Annual", "Sick", "Maternity", "Study", etc.
    start_date: date
    end_date: date
    # Caller must supply days_count: the school calendar may exclude weekends
    # and public holidays, so the server cannot compute it reliably here.
    days_count: int
    reason: str | None = None

    @field_validator("days_count")
    @classmethod
    def positive_days(cls, v: int) -> int:
        if v < 1:
            raise ValueError("days_count must be at least 1")
        return v


class LeaveRead(BaseModel):
    id: uuid.UUID
    staff_member_id: uuid.UUID
    leave_type: str
    start_date: date
    end_date: date
    days_count: int
    reason: str | None
    status: LeaveStatus
    approved_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaveReview(BaseModel):
    """Body for the approve/reject endpoint."""
    status: LeaveStatus
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def terminal_status_only(cls, v: LeaveStatus) -> LeaveStatus:
        if v not in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
            raise ValueError("status must be APPROVED or REJECTED")
        return v


# Resolve forward references for StaffMemberDetail
StaffMemberDetail.model_rebuild()
