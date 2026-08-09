from __future__ import annotations
import uuid
from datetime import date, datetime
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
