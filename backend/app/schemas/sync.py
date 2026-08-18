"""
Schemas for the offline sync outbox endpoint and conflict resolution.

FLOW
----
Client (Dexie WriteOutbox) → POST /sync/outbox
  Each item carries offline_session_started_at — the moment the offline
  session began. Server compares this to Score.submitted_at to detect
  concurrent edits.

Result per item:
  "applied"  → write accepted, entity updated
  "conflict" → server version is newer; OfflineSyncConflict row created
"""
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class OutboxScoreData(BaseModel):
    """Payload for entity_type = "score"."""
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    raw_score: Decimal


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
    entity_type: Literal["score"]
    offline_session_started_at: datetime
    data: OutboxScoreData
    # Only used/required when the assessment's term has results_locked=True —
    # same contract as BulkScoreSubmit.override_reason, honoured only if the
    # caller holds assessments.approve_scores (services/sync.py routes this
    # through the same check_term_lock_override() submit_scores itself uses).
    override_reason: str | None = None


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
    merged_data: OutboxScoreData | None = None
    # Same contract as OutboxItem.override_reason — only needed when
    # CLIENT_WINS/MERGED targets a locked term.
    override_reason: str | None = None
