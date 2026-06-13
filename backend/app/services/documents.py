"""
DocumentRecord service — metadata tracking for uploaded files.

Storage path: /uploads/documents/{school_id}/{entity_type}/{entity_id}/{filename}
In production (R2), the path is a CDN key in the same structure.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.documents import DocumentRecord
from app.schemas.documents import DocumentRecordRead

MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}


def _upload_path(school_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID) -> Path:
    root = Path(settings.local_upload_dir) / "documents" / str(school_id) / entity_type / str(entity_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _to_read(r: DocumentRecord) -> DocumentRecordRead:
    return DocumentRecordRead.model_validate(r)


async def upload_document(
    entity_type: str,
    entity_id: uuid.UUID,
    document_type: str,
    file: UploadFile,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> DocumentRecordRead:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"File type not allowed: {file.content_type}")
    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 10 MB limit.")

    dest_dir = _upload_path(school_id, entity_type, entity_id)
    safe_name = Path(file.filename or "upload").name
    dest = dest_dir / safe_name
    dest.write_bytes(raw)

    rel_path = f"documents/{school_id}/{entity_type}/{entity_id}/{safe_name}"
    rec = DocumentRecord(
        school_id=school_id,
        entity_type=entity_type,
        entity_id=entity_id,
        document_type=document_type,
        file_path=rel_path,
        file_name=safe_name,
        file_size=len(raw),
        mime_type=file.content_type,
        uploaded_by_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    await db.flush()
    return _to_read(rec)


async def list_documents(
    entity_type: str, entity_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[DocumentRecordRead]:
    rows = (await db.scalars(
        select(DocumentRecord)
        .where(
            DocumentRecord.entity_type == entity_type,
            DocumentRecord.entity_id == entity_id,
            DocumentRecord.school_id == school_id,
        )
        .order_by(DocumentRecord.created_at.desc())
    )).all()
    return [_to_read(r) for r in rows]


async def get_document(
    doc_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> DocumentRecord:
    rec = await db.scalar(
        select(DocumentRecord).where(
            DocumentRecord.id == doc_id, DocumentRecord.school_id == school_id
        )
    )
    if not rec:
        raise HTTPException(404, "Document not found.")
    return rec


async def delete_document(
    doc_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    rec = await get_document(doc_id, school_id, db)
    full_path = Path(settings.local_upload_dir) / rec.file_path
    if full_path.exists():
        full_path.unlink()
    await db.delete(rec)
