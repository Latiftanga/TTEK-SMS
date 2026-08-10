"""GET /students/{student_id}/diagnostics — read-only diagnostic-assessment
history, full lifetime (no term filter — diagnostics aren't term-bound the
way routine assessments are).

Permission is assessments.view (matching students_transcript.py/
report_cards.py), not students.view — this exposes score data, same bar as
pulling a report card or transcript.

Scoped via core/student_scope.py::assert_can_view_student() inside
services/diagnostics.py::list_diagnostic_records() (same boundary as the
rest of the Students module).
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.diagnostics import DiagnosticRecordRead
from app.services.diagnostics import list_diagnostic_records

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}/diagnostics", response_model=list[DiagnosticRecordRead])
async def get_diagnostics(
    student_id: uuid.UUID,
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await list_diagnostic_records(student_id, school_id, user_id, db)
