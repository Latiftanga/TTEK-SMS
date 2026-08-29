import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.attendance_excuse import ExcuseStatus


class ExcuseRequestCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> "ExcuseRequestCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ExcuseRequestRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    start_date: date
    end_date: date
    reason: str
    status: ExcuseStatus
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ExcuseRequestReview(BaseModel):
    """Body for the staff-side approve/reject endpoint."""
    status: ExcuseStatus
    review_notes: str | None = None
    # Only needed if any day in [start_date, end_date] falls in a
    # results_locked or non-current term — same contract as
    # AttendanceMarkRequest.override_reason.
    override_reason: str | None = None

    @field_validator("status")
    @classmethod
    def terminal_status_only(cls, v: ExcuseStatus) -> ExcuseStatus:
        if v not in (ExcuseStatus.APPROVED, ExcuseStatus.REJECTED):
            raise ValueError("status must be APPROVED or REJECTED")
        return v
