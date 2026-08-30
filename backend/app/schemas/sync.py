"""
Schemas for the offline sync outbox endpoint and conflict resolution.

FLOW
----
Client (Dexie WriteOutbox) → POST /sync/outbox
  Each item carries offline_session_started_at — the moment the offline
  session began. Server compares this to the entity's own "last write"
  timestamp (Score.submitted_at, AttendanceRecord.recorded_at) to detect
  concurrent edits.

Result per item:
  "applied"  → write accepted, entity updated
  "conflict" → server version is newer; OfflineSyncConflict row created

Two entity types today: "score" and "attendance". `data`'s shape is a plain
Union (not a Field(discriminator=...) union) since the discriminator
(`entity_type`) is a sibling field, not a field inside the union members
themselves — pydantic v2's smart-mode union matching already disambiguates
correctly since the two payload shapes share no confusable required-field
set, and _data_matches_entity_type() below is a defensive belt-and-braces
check on top of that.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.attendance import AttendanceStatus


class OutboxScoreData(BaseModel):
    """Payload for entity_type = "score"."""
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    raw_score: Decimal


class OutboxAttendanceData(BaseModel):
    """Payload for entity_type = "attendance". period_id: None = the
    always-available whole-day roll call (unchanged); a real SchoolPeriod id
    marks that one period instead — additive, never a replacement — only
    accepted when School.has_period_attendance is true (see
    services/attendance_shared.py::validate_period_marking, shared with the
    online mark_attendance() path so neither route has weaker rules)."""
    student_id: uuid.UUID
    school_calendar_id: uuid.UUID
    class_id: uuid.UUID
    status: AttendanceStatus
    notes: str | None = None
    period_id: uuid.UUID | None = None


class OutboxItem(BaseModel):
    # Both map to String(100) DB columns (OfflineSyncConflict.outbox_id,
    # OutboxProcessedItem.client_op_id) — bounded here so an oversized value
    # is a clean 422 instead of a raw IntegrityError (500).
    outbox_id: str = Field(max_length=100)
    # Client-generated (crypto.randomUUID()) once, when the write is first
    # queued — unlike outbox_id (a Dexie local auto-increment id, unique only
    # within one device), this is globally unique and safe to use as an
    # idempotency key (see OutboxProcessedItem).
    client_op_id: str = Field(max_length=100)
    entity_type: Literal["score", "attendance"]
    offline_session_started_at: datetime
    data: OutboxScoreData | OutboxAttendanceData
    # Only used/required when the entity's term has results_locked=True (or,
    # for attendance, also when the term isn't current) — same contract as
    # BulkScoreSubmit.override_reason/AttendanceMarkRequest.override_reason,
    # honoured only if the caller holds the matching bypass permission.
    override_reason: str | None = None

    @model_validator(mode="after")
    def _data_matches_entity_type(self) -> "OutboxItem":
        expected = OutboxScoreData if self.entity_type == "score" else OutboxAttendanceData
        if not isinstance(self.data, expected):
            raise ValueError(f"data does not match entity_type={self.entity_type!r}")
        return self


class OutboxSyncRequest(BaseModel):
    items: list[OutboxItem]


class OutboxItemResult(BaseModel):
    outbox_id: str
    status: Literal["applied", "conflict"]
    conflict_id: uuid.UUID | None = None


class ConflictRead(BaseModel):
    id: uuid.UUID
    outbox_id: str
    entity_type: str
    client_data: dict[str, Any]
    server_data: dict[str, Any]
    conflict_type: str
    resolution: str | None
    resolved_at: datetime | None
    resolved_by_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ConflictResolveRequest(BaseModel):
    resolution: Literal["CLIENT_WINS", "SERVER_WINS", "MERGED", "DISCARDED"]
    merged_data: OutboxScoreData | OutboxAttendanceData | None = None
    # Same contract as OutboxItem.override_reason — only needed when
    # CLIENT_WINS/MERGED targets a locked/non-current term.
    override_reason: str | None = None
