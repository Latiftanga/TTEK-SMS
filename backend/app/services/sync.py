"""
Offline sync processing — outbox ingestion and conflict resolution.

CONFLICT DETECTION
------------------
For entity_type="score":
  If Score.submitted_at > item.offline_session_started_at → the server received
  a newer write AFTER the offline session began → conflict.
  Otherwise → safe to apply the write (no concurrent edit since session start).

RESOLUTION ACTIONS
------------------
  CLIENT_WINS → re-apply the client's data (submit the offline score)
  SERVER_WINS / DISCARDED → mark resolved, keep server version unchanged
  MERGED → apply caller-supplied merged_data instead of either raw version
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import Assessment, Score, ScoreAuditLog
from app.models.documents import ConflictResolution, OfflineSyncConflict, OutboxProcessedItem
from app.models.students import Student
from app.schemas.sync import (
    ConflictRead, ConflictResolveRequest,
    OutboxItem, OutboxItemResult, OutboxScoreData,
)


def _conflict_read(c: OfflineSyncConflict) -> ConflictRead:
    return ConflictRead.model_validate(c)


async def _assert_score_target_in_school(
    data: OutboxScoreData, school_id: uuid.UUID, db: AsyncSession
) -> None:
    """assessment_id/student_id come straight from the offline outbox payload
    (or, for a conflict resolve, from previously-stored client_data/caller-
    supplied merged_data) — nothing upstream verifies they belong to the
    syncing user's own school. Without this, a lookup that finds no existing
    Score at this school (because the ids are actually a different school's)
    falls through to creating a brand-new Score row stamped with the
    caller's own school_id but pointing via FK at another school's real
    Assessment/Student — corrupting their data with a fabricated score."""
    assessment = await db.get(Assessment, data.assessment_id)
    if not assessment or assessment.school_id != school_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "assessment_id not found for this school.")
    student = await db.get(Student, data.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id not found for this school.")


async def _apply_score(
    data: OutboxScoreData,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    await _assert_score_target_in_school(data, school_id, db)
    now = datetime.now(timezone.utc)
    existing = await db.scalar(
        select(Score).where(
            Score.assessment_id == data.assessment_id,
            Score.student_id == data.student_id,
            Score.school_id == school_id,
        )
    )
    if existing:
        log = ScoreAuditLog(
            school_id=school_id,
            score_id=existing.id,
            changed_by_id=user_id,
            old_score=existing.raw_score,
            new_score=data.raw_score,
            changed_at=now,
        )
        db.add(log)
        existing.raw_score = data.raw_score
        existing.is_approved = False
        existing.cached_grade_label = None
        existing.entered_by_id = user_id
        existing.submitted_at = now
    else:
        score = Score(
            school_id=school_id,
            assessment_id=data.assessment_id,
            student_id=data.student_id,
            raw_score=data.raw_score,
            entered_by_id=user_id,
            submitted_at=now,
        )
        db.add(score)
        await db.flush()
        log = ScoreAuditLog(
            school_id=school_id,
            score_id=score.id,
            changed_by_id=user_id,
            old_score=None,
            new_score=data.raw_score,
            changed_at=now,
        )
        db.add(log)


async def _sync_score(
    item: OutboxItem,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> OutboxItemResult:
    # Idempotency: a retried or duplicated submission of the same client_op_id
    # (two drain triggers racing, or a client retry after a dropped response)
    # returns the recorded outcome instead of reprocessing it.
    processed = await db.scalar(
        select(OutboxProcessedItem).where(
            OutboxProcessedItem.school_id == school_id,
            OutboxProcessedItem.user_id == user_id,
            OutboxProcessedItem.client_op_id == item.client_op_id,
        )
    )
    if processed:
        return OutboxItemResult(
            outbox_id=item.outbox_id,
            status=processed.status,
            conflict_id=processed.conflict_id,
        )

    data = item.data
    offline_ts = item.offline_session_started_at
    if offline_ts.tzinfo is None:
        from datetime import timezone as tz
        offline_ts = offline_ts.replace(tzinfo=tz.utc)

    existing = await db.scalar(
        select(Score).where(
            Score.assessment_id == data.assessment_id,
            Score.student_id == data.student_id,
            Score.school_id == school_id,
        )
    )

    now = datetime.now(timezone.utc)

    if existing and existing.submitted_at and existing.submitted_at > offline_ts:
        conflict = OfflineSyncConflict(
            school_id=school_id,
            user_id=user_id,
            outbox_id=item.outbox_id,
            entity_type="score",
            client_data={
                "assessment_id": str(data.assessment_id),
                "student_id": str(data.student_id),
                "raw_score": str(data.raw_score),
            },
            server_data={
                "raw_score": str(existing.raw_score),
                "submitted_at": existing.submitted_at.isoformat(),
                "is_approved": existing.is_approved,
            },
            conflict_type="CONCURRENT_EDIT",
            created_at=now,
        )
        db.add(conflict)
        await db.flush()
        db.add(OutboxProcessedItem(
            school_id=school_id, user_id=user_id, client_op_id=item.client_op_id,
            status="conflict", conflict_id=conflict.id, processed_at=now,
        ))
        await db.flush()
        return OutboxItemResult(
            outbox_id=item.outbox_id,
            status="conflict",
            conflict_id=conflict.id,
        )

    await _apply_score(data, school_id, user_id, db)
    db.add(OutboxProcessedItem(
        school_id=school_id, user_id=user_id, client_op_id=item.client_op_id,
        status="applied", conflict_id=None, processed_at=now,
    ))
    await db.flush()
    return OutboxItemResult(outbox_id=item.outbox_id, status="applied")


async def process_outbox(
    items: list[OutboxItem],
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[OutboxItemResult]:
    return [await _sync_score(item, school_id, user_id, db) for item in items]


async def list_conflicts(
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[ConflictRead]:
    rows = await db.scalars(
        select(OfflineSyncConflict)
        .where(
            OfflineSyncConflict.school_id == school_id,
            OfflineSyncConflict.user_id == user_id,
            OfflineSyncConflict.resolution.is_(None),
        )
        .order_by(OfflineSyncConflict.created_at)
    )
    return [_conflict_read(c) for c in rows]


async def resolve_conflict(
    conflict_id: uuid.UUID,
    req: ConflictResolveRequest,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ConflictRead:
    conflict = await db.scalar(
        select(OfflineSyncConflict).where(
            OfflineSyncConflict.id == conflict_id,
            OfflineSyncConflict.school_id == school_id,
        )
    )
    if not conflict:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conflict not found.")
    if conflict.resolution is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Conflict is already resolved.")

    now = datetime.now(timezone.utc)

    if req.resolution == "CLIENT_WINS":
        client_data = OutboxScoreData(**conflict.client_data)
        await _apply_score(client_data, school_id, user_id, db)
    elif req.resolution == "MERGED" and req.merged_data:
        await _apply_score(req.merged_data, school_id, user_id, db)

    conflict.resolution = ConflictResolution(req.resolution)
    conflict.resolved_at = now
    conflict.resolved_by_id = user_id
    await db.flush()
    return _conflict_read(conflict)
