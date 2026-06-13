from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ImportRowResult(BaseModel):
    row: int
    ref: str | None          # admission_number / staff_number / whatever the row key is
    status: str              # "created" | "failed"
    error: str | None


class ImportBatchResult(BaseModel):
    batch_id: uuid.UUID
    total_rows: int
    created: int
    failed: int
    errors: list[ImportRowResult]


class DocumentRecordRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    document_type: str
    file_name: str
    file_size: int | None
    mime_type: str | None
    uploaded_by_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}
