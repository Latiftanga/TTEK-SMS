from __future__ import annotations
import uuid
from datetime import date

from pydantic import BaseModel, Field


class LessonPlanCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    week_start_date: date  # any date in the target week — normalized server-side
    topic: str = Field(min_length=1, max_length=300)
    content_standard: str | None = Field(default=None, max_length=300)
    indicator: str | None = Field(default=None, max_length=300)
    learning_objectives: str | None = None
    core_competencies: str | None = Field(default=None, max_length=300)
    teaching_resources: str | None = None
    activities: str | None = None
    assessment_strategy: str | None = None
    reflection_notes: str | None = None


class LessonPlanUpdate(BaseModel):
    topic: str | None = Field(default=None, min_length=1, max_length=300)
    content_standard: str | None = Field(default=None, max_length=300)
    indicator: str | None = Field(default=None, max_length=300)
    learning_objectives: str | None = None
    core_competencies: str | None = Field(default=None, max_length=300)
    teaching_resources: str | None = None
    activities: str | None = None
    assessment_strategy: str | None = None
    reflection_notes: str | None = None


class LessonPlanRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    week_start_date: date
    topic: str
    content_standard: str | None
    indicator: str | None
    learning_objectives: str | None
    core_competencies: str | None
    teaching_resources: str | None
    activities: str | None
    assessment_strategy: str | None
    reflection_notes: str | None
    created_by_id: uuid.UUID
    model_config = {"from_attributes": True}


class LessonPlanAiDraftRequest(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    topic: str = Field(min_length=1, max_length=300)


class LessonPlanAiDraftResponse(BaseModel):
    draft_text: str
