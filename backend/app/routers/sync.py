"""
Offline sync router — outbox ingestion and conflict resolution.

Gated on require_permission_any([("assessments","enter_scores"),
("attendance","record")]) — the shared minimum bar for either write path
this endpoint stands in for (submit_scores / mark_attendance), not just
require_auth. A bare "logged in" check would let a student/guardian portal
login (which authenticates fine but holds no staff permissions at all)
POST directly to /sync/outbox and write arbitrary Score/AttendanceRecord
rows. services/sync.py and services/sync_attendance.py each then further
scope every individual write to the caller's own ClassTeacher/SubjectTeacher
assignment, exactly like the online submit_scores/mark_attendance do.

Conflict list is scoped to the authenticated user — teachers only see their
own conflicts; admins use the same endpoint but are shown only theirs too.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission_any
from app.schemas.sync import (
    ConflictRead, ConflictResolveRequest,
    OutboxItemResult, OutboxSyncRequest,
)
from app.services import sync as sync_svc

router = APIRouter(prefix="/sync", tags=["sync"])

_SYNC_PERMISSIONS = [("assessments", "enter_scores"), ("attendance", "record")]


@router.post("/outbox", response_model=list[OutboxItemResult], status_code=200)
async def process_outbox(
    req: OutboxSyncRequest,
    ids=Depends(require_permission_any(_SYNC_PERMISSIONS)),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.process_outbox(req.items, school_id, user_id, db)


@router.get("/conflicts", response_model=list[ConflictRead])
async def list_conflicts(
    ids=Depends(require_permission_any(_SYNC_PERMISSIONS)),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.list_conflicts(school_id, user_id, db)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictRead)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    req: ConflictResolveRequest,
    ids=Depends(require_permission_any(_SYNC_PERMISSIONS)),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.resolve_conflict(conflict_id, req, school_id, user_id, db)
