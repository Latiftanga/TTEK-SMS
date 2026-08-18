"""
Offline sync router — outbox ingestion and conflict resolution.

Gated on assessments.enter_scores — the same minimum bar submit_scores
itself requires (routers/scoring.py) — not just require_auth. This is the
single online route into services/scoring.py's write logic, so it must be
at least as restrictive as the endpoint it stands in for: a bare "logged in"
check would let a student/guardian portal login (which authenticates fine
but holds no staff permissions at all) POST directly to /sync/outbox and
write arbitrary Score rows. services/sync.py itself then further scopes each
individual write to the caller's own ClassTeacher/SubjectTeacher assignment,
exactly like submit_scores does.

Conflict list is scoped to the authenticated user — teachers only see their
own conflicts; admins use the same endpoint but are shown only theirs too.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.sync import (
    ConflictRead, ConflictResolveRequest,
    OutboxItemResult, OutboxSyncRequest,
)
from app.services import sync as sync_svc

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/outbox", response_model=list[OutboxItemResult], status_code=200)
async def process_outbox(
    req: OutboxSyncRequest,
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.process_outbox(req.items, school_id, user_id, db)


@router.get("/conflicts", response_model=list[ConflictRead])
async def list_conflicts(
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.list_conflicts(school_id, user_id, db)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictRead)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    req: ConflictResolveRequest,
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.resolve_conflict(conflict_id, req, school_id, user_id, db)
