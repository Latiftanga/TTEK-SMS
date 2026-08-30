"""
Curriculum material upload/list/delete — PDF-only (textbook/teacher-manual/
syllabus), scoped to a class+subject via the existing ClassSubject junction.
No entity_type/entity_id polymorphism like DocumentRecord — this is a
dedicated table with its own storage path, since the access-control shape
is genuinely different (admin-uploaded, broadly teacher-readable reference
material, not per-student/per-staff owned) — see models/curriculum_materials.py.

MIME/magic-byte validation is intentionally narrower than services/
documents.py's (PDF only) — text extraction (services/curriculum_extraction.py)
only knows how to read PDFs; a DOCX/image upload here would silently never
get grounded content.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.academic import ClassSubject
from app.models.curriculum_materials import CurriculumMaterial, ExtractionStatus
from app.schemas.curriculum_materials import CurriculumMaterialRead

MAX_FILE_NAME_LEN = 200
MAX_DOCUMENT_TYPE_LEN = 100
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB — a real textbook PDF needs more than Documents' 10MB cap

_PDF_MAGIC = b"%PDF-"


def _looks_like_pdf(raw: bytes) -> bool:
    return raw.startswith(_PDF_MAGIC)


def _upload_path(school_id: uuid.UUID, class_subject_id: uuid.UUID) -> Path:
    root = Path(settings.secure_upload_dir) / "curriculum_materials" / str(school_id) / str(class_subject_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _to_read(m: CurriculumMaterial) -> CurriculumMaterialRead:
    return CurriculumMaterialRead.model_validate(m)


async def _assert_class_subject_owned(class_subject_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    exists = await db.scalar(
        select(ClassSubject.id).where(ClassSubject.id == class_subject_id, ClassSubject.school_id == school_id)
    )
    if not exists:
        raise HTTPException(404, "Class/subject not found.")


async def upload_material(
    class_subject_id: uuid.UUID,
    document_type: str,
    file: UploadFile,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> CurriculumMaterialRead:
    await _assert_class_subject_owned(class_subject_id, school_id, db)

    if file.content_type != "application/pdf":
        raise HTTPException(415, f"Only PDF files are accepted for curriculum materials, got: {file.content_type}")
    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 50 MB limit.")
    if not _looks_like_pdf(raw):
        raise HTTPException(415, "File content doesn't match its declared type.")

    original_name = Path(file.filename or "upload.pdf").name
    if len(original_name) > MAX_FILE_NAME_LEN:
        raise HTTPException(422, f"Filename must be {MAX_FILE_NAME_LEN} characters or fewer.")
    if len(document_type) > MAX_DOCUMENT_TYPE_LEN:
        raise HTTPException(422, f"document_type must be {MAX_DOCUMENT_TYPE_LEN} characters or fewer.")

    mat_id = uuid.uuid4()
    stored_name = f"{mat_id}_{original_name}"
    rel_path = f"curriculum_materials/{school_id}/{class_subject_id}/{stored_name}"

    # DB row committed before the disk write — same "orphaned file with no
    # row to find it by" fix already applied to documents.py::upload_document.
    mat = CurriculumMaterial(
        id=mat_id,
        school_id=school_id,
        class_subject_id=class_subject_id,
        document_type=document_type,
        file_path=rel_path,
        file_name=original_name,
        file_size=len(raw),
        mime_type=file.content_type,
        uploaded_by_id=user_id,
        created_at=datetime.now(timezone.utc),
        extraction_status=ExtractionStatus.PENDING,
    )
    db.add(mat)
    await db.flush()

    try:
        dest_dir = _upload_path(school_id, class_subject_id)
        (dest_dir / stored_name).write_bytes(raw)
    except OSError:
        await db.delete(mat)
        await db.flush()
        raise HTTPException(500, "Could not save the uploaded file.")

    return _to_read(mat)


async def list_materials(
    class_subject_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> list[CurriculumMaterialRead]:
    rows = await db.scalars(
        select(CurriculumMaterial)
        .where(CurriculumMaterial.class_subject_id == class_subject_id, CurriculumMaterial.school_id == school_id)
        .order_by(CurriculumMaterial.created_at.desc())
    )
    return [_to_read(r) for r in rows]


async def delete_material(material_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    mat = await db.scalar(
        select(CurriculumMaterial).where(CurriculumMaterial.id == material_id, CurriculumMaterial.school_id == school_id)
    )
    if not mat:
        raise HTTPException(404, "Curriculum material not found.")

    file_path = Path(settings.secure_upload_dir) / mat.file_path
    await db.delete(mat)
    await db.flush()
    file_path.unlink(missing_ok=True)
