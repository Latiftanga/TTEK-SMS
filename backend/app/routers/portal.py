"""
Parent/student portal — read-only self-service access for ADMISSION_ID users.

Two checks gate every portal request:
  1. The caller must be a student user (User.student_id is not None).
  2. Report cards additionally require at least one published Assessment for
     the class+term (Assessment.is_published = True) — see
     services/portal.py::is_report_published.

GET /portal/me and GET /portal/term-enrollments exist so the frontend can
discover the logged-in student's own identity and which enrollment_id to
request a report card for — before these existed there was no way for a
portal user to find that out at all.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.models.auth import User
from app.models.students import TermEnrollment
from app.schemas.portal import PortalProfile, PortalTermEnrollmentRead
from app.services import portal as portal_svc
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


@router.get("/me", response_model=PortalProfile)
async def get_my_profile(
    auth=Depends(_require_portal_user),
    db: AsyncSession = Depends(get_db),
):
    _, school_id, student_id = auth
    return await portal_svc.get_my_profile(student_id, school_id, db)


@router.get("/term-enrollments", response_model=list[PortalTermEnrollmentRead])
async def list_my_term_enrollments(
    auth=Depends(_require_portal_user),
    db: AsyncSession = Depends(get_db),
):
    _, school_id, student_id = auth
    return await portal_svc.list_my_term_enrollments(student_id, school_id, db)


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

    if not await portal_svc.is_report_published(student_id, te.academic_term_id, school_id, db):
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
