from __future__ import annotations
import uuid
from datetime import date, datetime
from pydantic import BaseModel, field_validator
from app.models.staff import EmploymentType, Gender, MaritalStatus, StaffType
from app.models.staff_history import LeaveStatus


class StaffCategoryCreate(BaseModel):
    name: str
    code: str
    staff_type: StaffType | None = None

    @field_validator("name", "code")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class StaffCategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    staff_type: StaffType | None
    is_template: bool
    is_active: bool
    school_id: uuid.UUID | None
    model_config = {"from_attributes": True}


class StaffRankCreate(BaseModel):
    title: str
    category_id: uuid.UUID

    @field_validator("title")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class StaffRankRead(BaseModel):
    id: uuid.UUID
    title: str
    category_id: uuid.UUID
    is_template: bool
    is_active: bool
    school_id: uuid.UUID | None
    model_config = {"from_attributes": True}


class PositionRead(BaseModel):
    id: uuid.UUID
    name: str
    model_config = {"from_attributes": True}


class StaffMemberCreate(BaseModel):
    staff_number: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    category_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    employment_type: EmploymentType | None = None
    marital_status: MaritalStatus | None = None
    national_id: str | None = None
    ssnit_number: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    position_ids: list[uuid.UUID] = []
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
    category_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    employment_type: EmploymentType | None = None
    marital_status: MaritalStatus | None = None
    national_id: str | None = None
    ssnit_number: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    position_ids: list[uuid.UUID] | None = None  # None = no change; [] = clear all
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
    category_id: uuid.UUID | None
    category_name: str | None
    staff_type: StaffType | None
    gender: Gender | None
    employment_type: EmploymentType | None
    phone: str | None
    email: str | None
    position_ids: list[uuid.UUID]
    position_names: list[str]
    is_active: bool
    joined_date: date | None
    photo_url: str | None = None


class StaffMemberDetail(StaffMemberSummary):
    """Full profile view — includes nested sub-records."""
    date_of_birth: date | None
    marital_status: MaritalStatus | None
    national_id: str | None
    ssnit_number: str | None
    address: str | None
    photo_path: str | None
    has_account: bool
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


class QualificationUpdate(BaseModel):
    institution: str | None = None
    qualification_type: str | None = None
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
    from_rank_id: uuid.UUID | None = None
    to_rank_id: uuid.UUID
    effective_date: date
    reason: str | None = None


class PromotionUpdate(BaseModel):
    from_rank_id: uuid.UUID | None = None
    to_rank_id: uuid.UUID | None = None
    effective_date: date | None = None
    reason: str | None = None


class PromotionRead(BaseModel):
    id: uuid.UUID
    staff_member_id: uuid.UUID
    from_rank_id: uuid.UUID | None
    to_rank_id: uuid.UUID | None
    from_rank_title: str | None = None
    to_rank_title: str | None = None
    effective_date: date
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


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
    staff_name: str | None = None
    staff_number: str | None = None
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

class TempPasswordResult(BaseModel):
    temporary_password: str
    display_name: str


# ── Responsibilities ──────────────────────────────────────────────────────────

class ClassTeacherAssignment(BaseModel):
    class_id: uuid.UUID
    class_name: str
    academic_year_id: uuid.UUID
    academic_year_name: str
    is_active: bool


class SubjectAssignment(BaseModel):
    class_id: uuid.UUID
    class_name: str
    subject_id: uuid.UUID
    subject_name: str
    academic_year_id: uuid.UUID
    academic_year_name: str
    is_active: bool


class HouseAssignment(BaseModel):
    house_id: uuid.UUID
    house_name: str
    house_code: str
    academic_year_id: uuid.UUID
    academic_year_name: str
    is_active: bool


class StaffResponsibilities(BaseModel):
    class_teacher: ClassTeacherAssignment | None
    subject_assignments: list[SubjectAssignment]
    house_assignments: list[HouseAssignment]
