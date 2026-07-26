"""Year-end outcomes — graduation/withdrawal/transfer (exit) and
promotion/repetition/demotion (progression). Literal-path endpoints, mounted
at the same /students prefix as students.py. See students.py's module
docstring for the full file split.

ACCESS CONTROL
--------------
GET  /students/graduation          students.edit
POST /students/graduation/bulk     students.edit
POST /students/promotions/bulk     students.edit
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.student_lifecycle import (
    BulkGraduateRequest, BulkGraduateResult,
    BulkPromoteRequest, BulkPromoteResult,
    GraduationRecordRead,
)
from app.services import graduation as graduation_svc
from app.services import promotion as promotion_svc

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/graduation", response_model=list[GraduationRecordRead])
async def list_graduation_records(
    academic_year_id: uuid.UUID | None = Query(None),
    student_id: uuid.UUID | None = Query(None),
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """List graduation records, optionally filtered by academic year and/or student."""
    _, school_id = ids
    return await graduation_svc.list_graduation_records(
        school_id, db, academic_year_id=academic_year_id, student_id=student_id,
    )


@router.post("/graduation/bulk", response_model=BulkGraduateResult, status_code=201)
async def bulk_graduate(
    req: BulkGraduateRequest,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Process year-end exit outcomes (graduated/withdrawn/transferred) for a batch of students."""
    user_id, school_id = ids
    return await graduation_svc.process_bulk_graduation(req, user_id, school_id, db)


@router.post("/promotions/bulk", response_model=BulkPromoteResult, status_code=201)
async def bulk_promote(
    req: BulkPromoteRequest,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Process year-end progression outcomes (promoted/repeated/demoted) for a batch of students."""
    user_id, school_id = ids
    return await promotion_svc.process_bulk_promotion(req, user_id, school_id, db)
