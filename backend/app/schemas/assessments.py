from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator


class AssessmentUpdate(BaseModel):
    description: str | None = None
    max_score: Decimal | None = None
    due_date: date | None = None
    override_reason: str | None = None


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


class AssessmentUnpublishRequest(BaseModel):
    """reason is always required — unlike a locked-term override (only
    required when the term happens to be locked), reversing a publish is
    itself the thing worth an audit trail, regardless of lock state."""
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A reason is required to unpublish an assessment.")
        return v


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
