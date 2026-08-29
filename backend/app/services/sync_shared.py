"""
Shared helpers between services/sync.py (Score offline sync) and
services/sync_attendance.py (Attendance offline sync) — split out to avoid
a circular import (sync.py's process_outbox/resolve_conflict need to call
into sync_attendance.py, which itself needs these same two helpers).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import OutboxProcessedItem

# A client can't have been "offline" starting in the future — capping here
# stops offline_session_started_at being used to defeat conflict detection
# (a far-future value would make `existing.submitted_at/recorded_at > offline_ts`
# evaluate False for any real value, silently skipping the conflict check).
# Some clock skew between client and server is expected and harmless, so
# this clamps rather than rejecting outright.
_MAX_FUTURE_SKEW = timedelta(minutes=5)


async def find_processed_item(
    school_id: uuid.UUID, user_id: uuid.UUID, client_op_id: str, db: AsyncSession,
) -> OutboxProcessedItem | None:
    """Idempotency lookup — a retried or duplicated submission of the same
    client_op_id (two drain triggers racing, or a client retry after a
    dropped response) must return the recorded outcome, not reprocess it."""
    return await db.scalar(
        select(OutboxProcessedItem).where(
            OutboxProcessedItem.school_id == school_id,
            OutboxProcessedItem.user_id == user_id,
            OutboxProcessedItem.client_op_id == client_op_id,
        )
    )


def clamp_session_start(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return now if ts > now + _MAX_FUTURE_SKEW else ts
