from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator


class BehaviourRecordCreate(BaseModel):
    student_id: uuid.UUID
    academic_term_id: uuid.UUID
    incident_type: str
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    action_taken: str | None = None
    incident_date: date

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
    format: str


class BulkReportRequest(BaseModel):
    class_id: uuid.UUID
    academic_term_id: uuid.UUID
    format: Literal["BASIC", "SHS"] = "BASIC"


class BulkReportJobRead(BaseModel):
    job_id: str
    class_id: uuid.UUID
    academic_term_id: uuid.UUID
    format: str
    status: str   # "queued" | "done" | "error"
    download_url: str | None = None
