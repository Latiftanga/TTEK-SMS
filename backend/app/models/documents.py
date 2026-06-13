"""
Group 10 — Documents, bulk imports, graduation, and offline sync conflict log.

Tables in this group:
  document_record      — metadata for uploaded files (path → local storage or R2)
  import_batch         — tracks a bulk import job (students, staff, scores)
  import_row           — individual row results within a batch
  graduation_record    — outcome for each student at year-end processing
  offline_sync_conflict — conflict log when an offline write conflicts with server state

DOCUMENT STORAGE NOTE
----------------------
DocumentRecord stores only the file path, not the file content.
Storage backend is LOCAL (/uploads) in development and Cloudflare R2 in production.
Switching backends requires no schema change — only the path format changes.
Report cards are NEVER stored; they are generated on demand by WeasyPrint and
streamed directly to the browser.

OFFLINE SYNC NOTE
-----------------
When a teacher submits scores offline (e.g. on a laptop without internet),
the client sends offline_session_started_at alongside the score data.
The server compares this timestamp to when the score was last modified.
If the server version is newer, a conflict is written to offline_sync_conflict
and the teacher is shown a diff to resolve manually.
"""
from __future__ import annotations
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, SchoolScopedMixin


class ImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class GraduationType(str, enum.Enum):
    PROMOTED = "PROMOTED"
    GRADUATED = "GRADUATED"
    REPEATED = "REPEATED"
    WITHDRAWN = "WITHDRAWN"
    TRANSFERRED = "TRANSFERRED"


class ConflictResolution(str, enum.Enum):
    CLIENT_WINS = "CLIENT_WINS"
    SERVER_WINS = "SERVER_WINS"
    MERGED = "MERGED"
    DISCARDED = "DISCARDED"


class DocumentRecord(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """Metadata-only record for uploaded files — path points to local storage or R2."""
    __tablename__ = "document_record"

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ImportBatch(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "import_batch"

    import_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus, name="importstatus"), default=ImportStatus.PENDING, nullable=False
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    initiated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ImportRow(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "import_row"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class GraduationRecord(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "graduation_record"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_year.id"), nullable=False
    )
    graduation_type: Mapped[GraduationType] = mapped_column(
        SAEnum(GraduationType, name="graduationtype"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )


class OfflineSyncConflict(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Written when server detects a conflict between offline data and server state.
    Offline score sync always sends offline_session_started_at — server checks this.
    """
    __tablename__ = "offline_sync_conflict"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outbox_id: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    client_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    server_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution: Mapped[ConflictResolution | None] = mapped_column(
        SAEnum(ConflictResolution, name="conflictresolution"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
