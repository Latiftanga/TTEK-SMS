from __future__ import annotations
import uuid
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator
from app.models.staff import Gender
from app.models.students import EnrollmentType, TransferStatus


ORPHAN_STATUSES = ("NONE", "HALF_ORPHAN", "FULL_ORPHAN")


class StudentCreate(BaseModel):
    # Omit or leave blank to auto-generate as {SCHOOL_CODE}/{YEAR}/{SEQ} (see
    # services/student.py::_next_admission_number). Supply a value to keep an
    # existing numbering scheme (bulk import, mid-year onboarding, etc.).
    admission_number: str | None = Field(default=None, max_length=50)
    first_name: str = Field(max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = Field(default=None, max_length=50)
    religion: str | None = Field(default=None, max_length=50)
    hometown: str | None = Field(default=None, max_length=100)
    residential_address: str | None = None
    nhis_number: str | None = Field(default=None, max_length=50)
    ghana_card_number: str | None = Field(default=None, max_length=50)
    is_boarding: bool = False
    orphan_status: str = Field(default="NONE", max_length=20)
    disability: str | None = Field(default=None, max_length=200)

    @field_validator("admission_number")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v is not None else None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class StudentUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = Field(default=None, max_length=50)
    religion: str | None = Field(default=None, max_length=50)
    hometown: str | None = Field(default=None, max_length=100)
    residential_address: str | None = None
    nhis_number: str | None = Field(default=None, max_length=50)
    ghana_card_number: str | None = Field(default=None, max_length=50)
    is_boarding: bool | None = None
    orphan_status: str | None = Field(default=None, max_length=20)
    disability: str | None = Field(default=None, max_length=200)
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
    blood_group: str | None = Field(default=None, max_length=10)
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
    address: str | None
    occupation: str | None
    relation_type: str
    is_primary: bool
    has_portal_access: bool = False


class GuardianCreate(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    phone: str = Field(max_length=20)
    email: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=100)
    address: str | None = None
    relation_type: str = Field(max_length=50)
    is_primary: bool = False


class GuardianUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=100)
    address: str | None = None
    relation_type: str | None = Field(default=None, max_length=50)
    is_primary: bool | None = None


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
    is_boarding: bool = False
    current_class_name: str | None = None
    current_class_id: uuid.UUID | None = None
    photo_url: str | None = None


class StudentDetail(StudentSummary):
    date_of_birth: date | None
    nationality: str | None
    religion: str | None
    hometown: str | None
    residential_address: str | None
    nhis_number: str | None
    ghana_card_number: str | None
    orphan_status: str
    disability: str | None
    photo_path: str | None
    has_portal_access: bool = False
    medical_record: MedicalRecordRead | None = None
    guardians: list[StudentGuardianRead] = []
    # Whether the caller can perform pastoral writes (profile/guardians/medical/
    # photo/enrollment) vs admin-tier actions (portal access, deactivate,
    # promotion) on THIS student specifically — see core/student_scope.py.
    # Only get_student() computes real values from the caller's identity; every
    # other StudentDetail response (a mutation that just succeeded) defaults
    # both to True.
    can_edit: bool = True
    can_manage: bool = True


class PortalAccessResult(BaseModel):
    has_portal_access: bool
    admission_number: str
    sms_sent: bool


class GuardianPortalAccessResult(BaseModel):
    has_portal_access: bool
    phone: str
    sms_sent: bool


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


class StudentClassAssignmentCreate(BaseModel):
    student_id: uuid.UUID
    class_id: uuid.UUID
    academic_year_id: uuid.UUID


class StudentClassAssignmentRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    class_id: uuid.UUID
    academic_year_id: uuid.UUID
    class_display_name: str
    is_active: bool
    created_at: datetime


class TermEnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    # Only honoured if the caller has fees.manage — otherwise a fee-gate block
    # is enforced regardless of what's supplied here. See
    # services/student_enrollment.py::create_term_enrollment.
    fee_waiver_reason: str | None = None


class TermEnrollmentRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    class_id: uuid.UUID | None = None
    class_display_name: str | None = None
    is_active: bool
    fee_waived: bool = False
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


class SubjectRegistrationBulkCreate(BaseModel):
    items: list[SubjectRegistrationItem]
    override_reason: str | None = None


class BulkRegisterCoreSubjectsRequest(BaseModel):
    academic_term_id: uuid.UUID
    override_reason: str | None = None


class BulkRegisterCoreSubjectsResult(BaseModel):
    registered: int
    skipped: int


class SubjectRosterStudent(BaseModel):
    student_id: uuid.UUID
    display_name: str
    admission_number: str
    enrolled: bool                        # has an active TermEnrollment this term
    is_registered: bool
    registration_id: uuid.UUID | None
    has_scores: bool                      # already has a Score for this subject this term


class SetSubjectRosterRequest(BaseModel):
    academic_term_id: uuid.UUID
    student_ids: list[uuid.UUID]          # full desired-checked set
    override_reason: str | None = None
    # Optimistic concurrency: the set of student_ids the caller saw as
    # already-registered when they fetched the roster. If the current DB
    # state no longer matches (someone else changed it in the meantime),
    # the write is rejected with 409 rather than silently overwriting their
    # change. None (the default) skips the check, for any caller that
    # doesn't track it.
    expected_registered_ids: list[uuid.UUID] | None = None


class SetSubjectRosterResult(BaseModel):
    registered: int
    removed: int
    skipped: int


class SubjectRegistrationRead(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    registration_type: str
    model_config = {"from_attributes": True}


class EnrollmentForReport(BaseModel):
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    admission_number: str
    display_name: str
    gender: str | None
    class_id: uuid.UUID | None
    class_display_name: str | None


class TransferRequestCreate(BaseModel):
    reason: str | None = None
    requesting_school_id: uuid.UUID | None = None


class BulkStudentClassAssignmentCreate(BaseModel):
    items: list[StudentClassAssignmentCreate]


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
    student_name: str | None = None
    admission_number: str | None = None
    status: TransferStatus
    reason: str | None
    requesting_school_id: uuid.UUID | None
    reviewed_at: datetime | None
    reviewed_by_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


StudentDetail.model_rebuild()

# Year-end outcome schemas (graduation/withdrawal/transfer, promotion/repetition/
# demotion) live in app.schemas.student_lifecycle.
