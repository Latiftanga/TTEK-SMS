from __future__ import annotations
import uuid
from datetime import date, datetime
from pydantic import BaseModel, field_validator
from app.models.staff import Gender
from app.models.students import EnrollmentType, TransferStatus


class StudentCreate(BaseModel):
    admission_number: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = None
    religion: str | None = None
    hometown: str | None = None
    residential_address: str | None = None

    @field_validator("admission_number", "first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class StudentUpdate(BaseModel):
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = None
    religion: str | None = None
    hometown: str | None = None
    residential_address: str | None = None
    is_active: bool | None = None


class MedicalRecordRead(BaseModel):
    id: uuid.UUID
    blood_group: str | None
    allergies: str | None
    chronic_conditions: str | None
    medications: str | None
    emergency_notes: str | None
    model_config = {"from_attributes": True}


class MedicalRecordUpsert(BaseModel):
    blood_group: str | None = None
    allergies: str | None = None
    chronic_conditions: str | None = None
    medications: str | None = None
    emergency_notes: str | None = None


class StudentGuardianRead(BaseModel):
    guardian_id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    email: str | None
    occupation: str | None
    relation_type: str
    is_primary: bool


class GuardianCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str | None = None
    occupation: str | None = None
    address: str | None = None
    relation_type: str
    is_primary: bool = False


class StudentSummary(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    admission_number: str
    first_name: str
    middle_name: str | None
    last_name: str
    display_name: str
    gender: Gender | None
    is_active: bool


class StudentDetail(StudentSummary):
    date_of_birth: date | None
    nationality: str | None
    religion: str | None
    hometown: str | None
    residential_address: str | None
    photo_path: str | None
    medical_record: MedicalRecordRead | None = None
    guardians: list[StudentGuardianRead] = []


class EnrollmentCreate(BaseModel):
    enrolled_at: date
    enrollment_type: EnrollmentType
    transfer_from_school: str | None = None


class EnrollmentRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    enrolled_at: date
    enrollment_type: EnrollmentType
    transfer_from_school: str | None
    model_config = {"from_attributes": True}


class TermEnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    class_id: uuid.UUID
    academic_term_id: uuid.UUID


class TermEnrollmentRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    class_id: uuid.UUID
    academic_term_id: uuid.UUID
    class_display_name: str
    is_active: bool
    created_at: datetime


class SubjectRegistrationItem(BaseModel):
    subject_id: uuid.UUID
    registration_type: str   # "CORE" | "ELECTIVE"

    @field_validator("registration_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        v = v.upper()
        if v not in ("CORE", "ELECTIVE"):
            raise ValueError("registration_type must be CORE or ELECTIVE")
        return v


class SubjectRegistrationRead(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    registration_type: str
    model_config = {"from_attributes": True}


class TransferRequestCreate(BaseModel):
    reason: str | None = None
    requesting_school_id: uuid.UUID | None = None


class BulkTermEnrollmentCreate(BaseModel):
    items: list[TermEnrollmentCreate]


class BulkEnrollResult(BaseModel):
    enrolled: int
    skipped: int


class TransferRequestReview(BaseModel):
    status: TransferStatus

    @field_validator("status")
    @classmethod
    def terminal_only(cls, v: TransferStatus) -> TransferStatus:
        allowed = {TransferStatus.APPROVED, TransferStatus.REJECTED, TransferStatus.WITHDRAWN}
        if v not in allowed:
            raise ValueError("status must be APPROVED, REJECTED, or WITHDRAWN")
        return v


class TransferRequestRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    status: TransferStatus
    reason: str | None
    requesting_school_id: uuid.UUID | None
    reviewed_at: datetime | None
    reviewed_by_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


StudentDetail.model_rebuild()
