"""
Manual correction of an AI-extracted CurriculumUnit — extraction accuracy on
a long document is unverified (see services/curriculum_unit_extraction.py's
own docstring), so this is the human-review safety valve, not an edge case.
Listing/triggering live on the material-scoped routes in
routers/curriculum_materials.py; this file exists only because a single
unit's own id, not its parent material's, is the natural key for a correction.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.curriculum_units import CurriculumUnitRead, CurriculumUnitUpdate
from app.services import curriculum_units as cu_svc

router = APIRouter(prefix="/curriculum-units", tags=["curriculum-units"])


@router.patch("/{unit_id}", response_model=CurriculumUnitRead)
async def update_unit(
    unit_id: uuid.UUID,
    req: CurriculumUnitUpdate,
    auth=Depends(require_permission("documents", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await cu_svc.update_unit(unit_id, req, school_id, db)
