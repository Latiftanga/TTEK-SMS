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
from app.core.dependencies import assert_self_or_permission
from app.core.student_scope import assert_can_view_student, assert_can_write_student
from app.models.documents import DocumentRecord
from app.models.staff import StaffMember
from app.models.students import Student
from app.schemas.documents import DocumentRecordRead

MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

# Magic-byte signatures for each allowed MIME type — the client-declared
# Content-Type header is trivially spoofable (any HTTP client can set it to
# anything), so the allowlist check above means nothing unless the actual
# file bytes are checked too. DOCX is a ZIP container and old-format DOC is
# an OLE compound file; both checked by their own container signature since
# neither format has a simpler distinguishing marker.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),   # full check (RIFF....WEBP) done inline below
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
    "application/msword": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}

# entity_type -> (model, school-scoping FK column) — the only entity types
# this system actually supports attaching documents to. Anything else is
# rejected outright rather than silently accepted as an arbitrary string.
_ENTITY_MODELS: dict[str, type] = {
    "student": Student,
    "staff": StaffMember,
}


def _upload_path(school_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID) -> Path:
    root = Path(settings.local_upload_dir) / "documents" / str(school_id) / entity_type / str(entity_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _to_read(r: DocumentRecord) -> DocumentRecordRead:
    return DocumentRecordRead.model_validate(r)


def _looks_like(content_type: str, raw: bytes) -> bool:
    if content_type == "image/webp":
        return raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    signatures = _MAGIC_BYTES.get(content_type)
    return signatures is not None and any(raw.startswith(sig) for sig in signatures)


async def _verify_entity_ownership(
    entity_type: str, entity_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> None:
    model = _ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(422, f"Unsupported entity type: {entity_type}")
    exists = await db.scalar(
        select(model.id).where(model.id == entity_id, model.school_id == school_id)
    )
    if not exists:
        raise HTTPException(404, f"No {entity_type} found with that id at this school.")


async def _assert_entity_access(
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """documents.view/manage alone used to be the whole check — no scoping
    to which specific student/staff member the caller is actually
    responsible for. CLASS_TEACHER holds documents.manage (needed to upload
    a form for their own student) but that let a class teacher upload/view/
    delete documents for ANY student school-wide, or even for a completely
    unrelated STAFF MEMBER's personal file (id card, contract) via
    entity_type=staff — the same unscoped-flat-permission gap already
    closed for Students/Attendance/Housing elsewhere in this codebase.

    A student's documents follow the exact same class-teacher scope as the
    rest of the Students module (core/student_scope.py — bypassed for
    students.delete holders and the same broad-access permissions that
    module already treats as unrestricted). A staff member's documents
    require the same self-or-staff.edit/view tier as touching that staff
    member's own HR record directly (core/dependencies.py::assert_self_or_permission)."""
    if entity_type == "student":
        if action == "manage":
            await assert_can_write_student(user_id, entity_id, db)
        else:
            await assert_can_view_student(user_id, entity_id, school_id, db)
    elif entity_type == "staff":
        perm_action = "edit" if action == "manage" else "view"
        await assert_self_or_permission(user_id, entity_id, "staff", perm_action, db)


async def upload_document(
    entity_type: str,
    entity_id: uuid.UUID,
    document_type: str,
    file: UploadFile,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> DocumentRecordRead:
    await _verify_entity_ownership(entity_type, entity_id, school_id, db)
    await _assert_entity_access(user_id, entity_type, entity_id, "manage", school_id, db)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"File type not allowed: {file.content_type}")
    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 10 MB limit.")
    if not _looks_like(file.content_type, raw):
        raise HTTPException(415, "File content doesn't match its declared type.")

    doc_id = uuid.uuid4()
    dest_dir = _upload_path(school_id, entity_type, entity_id)
    original_name = Path(file.filename or "upload").name
    # Prefix with the record's own id so two uploads with the same original
    # filename for the same entity never alias to one physical file on disk —
    # each DocumentRecord always owns a distinct, never-overwritten path.
    stored_name = f"{doc_id}_{original_name}"
    dest = dest_dir / stored_name
    dest.write_bytes(raw)

    rel_path = f"documents/{school_id}/{entity_type}/{entity_id}/{stored_name}"
    rec = DocumentRecord(
        id=doc_id,
        school_id=school_id,
        entity_type=entity_type,
        entity_id=entity_id,
        document_type=document_type,
        file_path=rel_path,
        file_name=original_name,
        file_size=len(raw),
        mime_type=file.content_type,
        uploaded_by_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    await db.flush()
    return _to_read(rec)


async def list_documents(
    entity_type: str, entity_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[DocumentRecordRead]:
    await _assert_entity_access(user_id, entity_type, entity_id, "view", school_id, db)
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
    doc_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession, *, action: str,
) -> DocumentRecord:
    rec = await db.scalar(
        select(DocumentRecord).where(
            DocumentRecord.id == doc_id, DocumentRecord.school_id == school_id
        )
    )
    if not rec:
        raise HTTPException(404, "Document not found.")
    # entity_type/entity_id are always "student"/"staff" here — only those
    # two ever get stored, gated by _verify_entity_ownership at upload time.
    await _assert_entity_access(user_id, rec.entity_type, rec.entity_id, action, school_id, db)
    return rec


async def delete_document(
    doc_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    rec = await get_document(doc_id, school_id, user_id, db, action="manage")
    full_path = Path(settings.local_upload_dir) / rec.file_path
    if full_path.exists():
        full_path.unlink()
    await db.delete(rec)
