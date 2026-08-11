from __future__ import annotations
import uuid
from decimal import Decimal

from pydantic import BaseModel, model_validator


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
    is_active: bool | None = None


class GradingScaleRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID | None
    name: str
    description: str | None
    is_active: bool
    is_default: bool
    grades: list[GradeRead] = []
    model_config = {"from_attributes": True}
