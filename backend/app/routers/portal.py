"""
Parent/student portal — read-only report card access for ADMISSION_ID users.

Two checks gate every portal request:
  1. The caller must be a student user (User.student_id is not None).
  2. At least one Assessment for the class+term must be published
     (Assessment.is_published = True) before the report is visible.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.models.academic import AcademicTerm
from app.models.assessments import Assessment
from app.models.auth import User
from app.models.students import StudentClassAssignment, TermEnrollment
from app.services import report_card as rc_svc
from app.services.pdf import render_report_card

router = APIRouter(prefix="/portal", tags=["portal"])


async def _require_portal_user(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID | None, uuid.UUID]:
    """Return (user_id, school_id, student_id); reject non-student callers."""
    user_id, school_id = ids
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated.")
    if user.student_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Portal access is limited to student accounts.",
        )
    return user_id, school_id, user.student_id


@router.get("/report-cards/{enrollment_id}")
async def portal_get_report_card(
    enrollment_id: uuid.UUID,
    format: str = Query("BASIC", pattern="^(BASIC|SHS|ECM)$"),
    auth=Depends(_require_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the PDF report card for the logged-in student.
    Returns 403 until the school publishes at least one assessment for the term.
    """
    _, school_id, student_id = auth

    te = await db.scalar(
        select(TermEnrollment).where(
            TermEnrollment.id == enrollment_id,
            TermEnrollment.school_id == school_id,
        )
    )
    if not te or te.student_id != student_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report card not found.")

    # Resolve the student's class for this academic year
    term = await db.get(AcademicTerm, te.academic_term_id)
    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == te.student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
        )
    ) if term else None

    published_count = await db.scalar(
        select(func.count())
        .select_from(Assessment)
        .where(
            Assessment.class_id == (sca.class_id if sca else None),
            Assessment.academic_term_id == te.academic_term_id,
            Assessment.school_id == school_id,
            Assessment.is_published.is_(True),
        )
    ) or 0
    if published_count == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Report card has not been published yet.")

    context = await rc_svc.assemble(enrollment_id, school_id, format, db)
    pdf_bytes = render_report_card(context, format)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="report_{context["admission_number"]}_{context["term_name"]}.pdf"'
            )
        },
    )
