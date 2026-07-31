"""
Programme-level summary — read-only, no mutation endpoints here at all.
Same prefix as academic_structure.py (already at the 300-line cap, no room
for a new route there) — same precedent as routers/subject_summary.py.

GET /academic/programmes/{programme_id}/summary   require_auth
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.schemas.academic import ProgrammeSummary
from app.services.programme_summary import get_programme_summary

router = APIRouter(prefix="/academic", tags=["academic"])


@router.get("/programmes/{programme_id}/summary", response_model=ProgrammeSummary)
async def programme_summary(
    programme_id: uuid.UUID,
    academic_year_id: uuid.UUID = Query(...),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await get_programme_summary(programme_id, academic_year_id, school_id, db)
