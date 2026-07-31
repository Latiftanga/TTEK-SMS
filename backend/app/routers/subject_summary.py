"""
Subject-level summary — read-only, no mutation endpoints here at all.
Same prefix as academic_structure.py (which is already at the 300-line
cap, no room for a new route there) — multiple router modules already
share one prefix this way, e.g. students.py/students_enrollment.py.

GET /academic/subjects/{subject_id}/summary   require_auth
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.schemas.academic import SubjectSummary
from app.services.subject_summary import get_subject_summary

router = APIRouter(prefix="/academic", tags=["academic"])


@router.get("/subjects/{subject_id}/summary", response_model=SubjectSummary)
async def subject_summary(
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID = Query(...),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await get_subject_summary(subject_id, academic_term_id, school_id, db)
