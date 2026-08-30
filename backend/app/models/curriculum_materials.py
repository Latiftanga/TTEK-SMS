"""
Curriculum materials — real textbook/teacher-manual/syllabus PDFs an admin/
HEAD uploads for a class+subject, so the AI lesson-planning assistant can
ground its output in the school's actual curriculum content instead of
generic knowledge.

Deliberately NOT modeled on DocumentRecord (models/documents.py) — that
table's access-control shape (_ENTITY_MODELS/_assert_entity_access in
services/documents.py) is built around per-student/per-staff ownership
scoping, which doesn't match this feature's real shape: admin-uploaded,
class+subject-scoped, broadly teacher-readable reference material. Storage
convention (secure_upload_dir) and MIME/magic-byte validation are still
reused from services/documents.py — just not the entity_type/entity_id
mechanism itself.

No embeddings/pgvector — retrieval is Postgres full-text search
(CurriculumMaterialChunk.search_vector, GIN-indexed), a deliberate scoping
decision (see the plan this was built from) over a heavier vector-search
stack this project has no infrastructure for yet.
"""
from __future__ import annotations
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

from app.models.base import Base, SchoolScopedMixin, UUIDPrimaryKey


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    FAILED = "FAILED"
    EMPTY = "EMPTY"  # real text-extraction ran, but zero pages had usable text


class CurriculumMaterial(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """One uploaded PDF (textbook/teacher manual/syllabus) for a class+subject.
    Text extraction runs as a background ARQ job — see
    services/curriculum_extraction.py — since a real textbook is too slow to
    process inline in the upload request."""
    __tablename__ = "curriculum_material"

    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subject.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Free text (e.g. "TEXTBOOK"/"TEACHER_MANUAL"/"SYLLABUS") — no enum,
    # matching DocumentRecord.document_type's own convention.
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(ExtractionStatus, name="extractionstatus"), nullable=False, default=ExtractionStatus.PENDING,
    )
    # Admin-facing reason when extraction_status is FAILED/EMPTY — e.g. "No
    # extractable text found — this looks like a scanned document." Never
    # silently left looking like extraction worked.
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CurriculumMaterialChunk(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """One page of usable extracted text from a CurriculumMaterial.
    search_vector powers full-text retrieval (services/curriculum_search.py)
    — populated from chunk_text at insert time, GIN-indexed (see migration)."""
    __tablename__ = "curriculum_material_chunk"

    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_material.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=False)
