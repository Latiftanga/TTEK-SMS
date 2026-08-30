from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.curriculum_materials import ExtractionStatus


class CurriculumMaterialRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_subject_id: uuid.UUID
    document_type: str
    file_name: str
    file_size: int | None
    mime_type: str | None
    uploaded_by_id: uuid.UUID
    created_at: datetime
    extraction_status: ExtractionStatus
    extraction_error: str | None
    model_config = {"from_attributes": True}


class CurriculumChunkResult(BaseModel):
    """One retrieved chunk, for grounding a prompt and citing the source
    back to the teacher — see services/curriculum_search.py."""
    material_id: uuid.UUID
    document_type: str
    file_name: str
    page_number: int
    chunk_text: str
