"""
Offline sync router — outbox ingestion and conflict resolution.

All endpoints require authentication only (no module permission beyond being
logged in), since teachers submit their own offline work.

Conflict list is scoped to the authenticated user — teachers only see their
own conflicts; admins use the same endpoint but are shown only theirs too.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.schemas.sync import (
    ConflictRead, ConflictResolveRequest,
    OutboxItemResult, OutboxSyncRequest,
)
from app.services import sync as sync_svc

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/outbox", response_model=list[OutboxItemResult], status_code=200)
async def process_outbox(
    req: OutboxSyncRequest,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.process_outbox(req.items, school_id, user_id, db)


@router.get("/conflicts", response_model=list[ConflictRead])
async def list_conflicts(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.list_conflicts(school_id, user_id, db)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictRead)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    req: ConflictResolveRequest,
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await sync_svc.resolve_conflict(conflict_id, req, school_id, user_id, db)
