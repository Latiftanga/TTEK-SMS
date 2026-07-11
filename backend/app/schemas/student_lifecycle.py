"""Year-end outcome schemas: graduation/withdrawal/transfer (exit) and
promotion/repetition/demotion (progression). See services/graduation.py and
services/promotion.py."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
from app.models.documents import GraduationType


# ── Year-end graduation / withdrawal / transfer (exit) ────────────────────────

class GraduationRecordCreate(BaseModel):
    student_id: uuid.UUID
    graduation_type: GraduationType
    notes: str | None = None


class BulkGraduateRequest(BaseModel):
    academic_year_id: uuid.UUID
    records: list[GraduationRecordCreate]
    deactivate_students: bool = True


class GraduationRecordRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    academic_year_id: uuid.UUID
    graduation_type: GraduationType
    notes: str | None
    processed_at: datetime
    processed_by_id: uuid.UUID
    model_config = {"from_attributes": True}


class BulkGraduateResult(BaseModel):
    processed: int
    skipped: int
    records: list[GraduationRecordRead]


# ── Year-end promotion / repetition / demotion (progression) ─────────────────

class PromotionRecordCreate(BaseModel):
    student_id: uuid.UUID
    graduation_type: GraduationType
    class_id: uuid.UUID
    notes: str | None = None

    @field_validator("graduation_type")
    @classmethod
    def _progression_only(cls, v: GraduationType) -> GraduationType:
        allowed = {GraduationType.PROMOTED, GraduationType.REPEATED, GraduationType.DEMOTED}
        if v not in allowed:
            raise ValueError(f"graduation_type must be one of {[t.value for t in allowed]}")
        return v


class BulkPromoteRequest(BaseModel):
    academic_year_id: uuid.UUID
    academic_term_id: uuid.UUID | None = None
    records: list[PromotionRecordCreate]


class BulkPromoteResult(BaseModel):
    processed: int
    skipped: int
    records: list[GraduationRecordRead]
