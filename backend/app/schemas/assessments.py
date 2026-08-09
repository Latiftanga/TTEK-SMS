from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


# ── Grading scale ─────────────────────────────────────────────────────────────

class GradeCreate(BaseModel):
    min_score: Decimal
    max_score: Decimal
    letter_grade: str
    label: str
    gpa_points: Decimal | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def range_valid(self) -> "GradeCreate":
        if self.min_score > self.max_score:
            raise ValueError("min_score must be ≤ max_score")
        return self


class GradeRead(BaseModel):
    id: uuid.UUID
    min_score: Decimal
    max_score: Decimal
    letter_grade: str
    label: str
    gpa_points: Decimal | None
    remarks: str | None
    model_config = {"from_attributes": True}


class GradingScaleCreate(BaseModel):
    name: str
    description: str | None = None
    is_default: bool = False


class GradingScaleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None


class GradingScaleRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID | None
    name: str
    description: str | None
    is_active: bool
    is_default: bool
    grades: list[GradeRead] = []
    model_config = {"from_attributes": True}


# ── Assessment type ───────────────────────────────────────────────────────────

class AssessmentTypeCreate(BaseModel):
    name: str
    code: str
    weight: Decimal

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: Decimal) -> Decimal:
        if v <= 0 or v > 100:
            raise ValueError("weight must be between 0.01 and 100")
        return v


class AssessmentTypeUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    weight: Decimal | None = None

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and (v <= 0 or v > 100):
            raise ValueError("weight must be between 0.01 and 100")
        return v


class AssessmentTypeRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    weight: Decimal
    is_active: bool
    model_config = {"from_attributes": True}


class AssessmentUpdate(BaseModel):
    description: str | None = None
    max_score: Decimal | None = None
    due_date: date | None = None
    override_reason: str | None = None


# ── Assessment ────────────────────────────────────────────────────────────────
# Identity is (class, subject, term, category, recorded_date) — not a typed
# name. description is optional supplementary detail; recorded_date is set
# server-side at creation (always today) and is never client-supplied.

class AssessmentCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    assessment_type_id: uuid.UUID
    academic_term_id: uuid.UUID
    description: str | None = None
    max_score: Decimal
    due_date: date | None = None


class AssessmentRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    assessment_type_id: uuid.UUID
    academic_term_id: uuid.UUID
    description: str | None
    recorded_date: date
    max_score: Decimal
    due_date: date | None
    is_published: bool
    model_config = {"from_attributes": True}


class AssessmentRosterStudent(BaseModel):
    """A student eligible to be scored for this assessment's subject —
    see services/subject_roster.py for what "eligible" means."""
    id: uuid.UUID
    display_name: str
    admission_number: str


# ── Scores ────────────────────────────────────────────────────────────────────

class ScoreSubmit(BaseModel):
    student_id: uuid.UUID
    raw_score: Decimal


class BulkScoreSubmit(BaseModel):
    scores: list[ScoreSubmit]
    # Only used/required when the assessment's term has results_locked=True.
    # Honoured only if the caller holds assessments.approve_scores.
    override_reason: str | None = None


class ScoreRead(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    raw_score: Decimal
    cached_grade_label: str | None
    is_approved: bool
    entered_by_id: uuid.UUID
    approved_by_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    model_config = {"from_attributes": True}


class ScoreApproveRequest(BaseModel):
    score_ids: list[uuid.UUID]
    # Only required when the assessment's term has results_locked=True.
    override_reason: str | None = None


# ── Behaviour ─────────────────────────────────────────────────────────────────

class BehaviourRecordCreate(BaseModel):
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    incident_type: str
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    action_taken: str | None = None
    incident_date: date
    # Only required when the term has results_locked=True.
    override_reason: str | None = None

    @field_validator("incident_type", "description")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class BehaviourRecordRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    incident_type: str
    description: str
    severity: str
    action_taken: str | None
    incident_date: date
    recorded_by_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class BehaviourAuditLogRead(BaseModel):
    id: uuid.UUID
    behaviour_record_id: uuid.UUID | None
    student_id: uuid.UUID
    action: str
    incident_type: str
    incident_date: date
    changed_by_id: uuid.UUID
    reason: str | None
    changed_at: datetime
    model_config = {"from_attributes": True}


class ScoreLineRead(BaseModel):
    subject_name: str
    assessment_type_name: str
    raw_score: Decimal
    max_score: Decimal
    grade_label: str | None


class ReportCardData(BaseModel):
    enrollment_id: uuid.UUID
    student_name: str
    admission_number: str
    class_name: str          # computed: level + year_group + programme + stream
    term_name: str
    academic_year_name: str
    class_teacher_name: str | None
    school_name: str
    logo_url: str | None
    scores: list[ScoreLineRead]
    total_score: Decimal
    max_possible: Decimal
    rank: int
    class_size: int
    days_present: int
    total_school_days: int
    behaviour_records: list[BehaviourRecordRead]
    qr_token: str


class BulkReportRequest(BaseModel):
    class_id: uuid.UUID
    academic_term_id: uuid.UUID


class BulkReportJobRead(BaseModel):
    job_id: str
    class_id: uuid.UUID
    academic_term_id: uuid.UUID
    status: str   # "queued" | "done" | "error"
    download_url: str | None = None


class BulkPublishRequest(BaseModel):
    class_id: uuid.UUID
    academic_term_id: uuid.UUID


class BulkPublishResult(BaseModel):
    published: int
    skipped_unapproved: int
    already_published: int


class MySubjectAssignment(BaseModel):
    """One (class, subject) combo the caller can create assessments/enter
    scores for — scoped to their own SubjectTeacher assignments unless they
    hold assessments.approve_scores, in which case every active ClassSubject
    pairing in the school is returned. Powers the Assessments page's
    cascading class → subject pickers."""
    class_id: uuid.UUID
    class_name: str
    subject_id: uuid.UUID
    subject_name: str
