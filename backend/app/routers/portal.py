"""
Parent/student portal — read-only self-service access for ADMISSION_ID
(student) and PHONE+guardian_id (guardian) users.

Two account shapes share this router:
  - Student (User.student_id set): every endpoint implicitly resolves to
    their own record — GET /portal/me is student-only.
  - Guardian (User.guardian_id set): can be linked to multiple children via
    StudentGuardian, so term-enrollments/report-cards require an explicit
    ?student_id= query param, verified against StudentGuardian before use.
    GET /portal/children lists the guardian's own linked students.

Report cards additionally require at least one published Assessment for the
class+term (Assessment.is_published = True) — see
services/portal.py::is_report_published.
"""
from __future__ import annotations
import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.models.auth import User
from app.models.students import TermEnrollment
from app.schemas.attendance_excuse import ExcuseRequestCreate, ExcuseRequestRead
from app.schemas.portal import PortalProfile, PortalTermEnrollmentRead
from app.services import attendance_excuse as excuse_svc
from app.services import portal as portal_svc
from app.services import report_card as rc_svc
from app.services.pdf import render_report_card

router = APIRouter(prefix="/portal", tags=["portal"])


async def _require_portal_user(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID | None, uuid.UUID]:
    """Return (user_id, school_id, student_id); reject non-student callers.

    Student-only — used by GET /portal/me, which has no equivalent "single
    profile" shape for a guardian (see GET /portal/children instead)."""
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


async def _require_portal_access(
    student_id: uuid.UUID | None = Query(
        None, description="Which child to view — required for a guardian account, ignored for a student account."
    ),
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Return (user_id, school_id, resolved_student_id) for a student viewing
    their own record OR a guardian viewing a linked child (student_id
    required, checked against StudentGuardian)."""
    user_id, school_id = ids
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated.")

    if user.student_id is not None:
        return user_id, school_id, user.student_id

    if user.guardian_id is not None:
        if student_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "student_id is required for a guardian account.")
        if not await portal_svc.is_guardian_of(user.guardian_id, student_id, school_id, db):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a guardian of this student.")
        return user_id, school_id, student_id

    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Portal access is limited to student and guardian accounts.",
    )


@router.get("/me", response_model=PortalProfile)
async def get_my_profile(
    auth=Depends(_require_portal_user),
    db: AsyncSession = Depends(get_db),
):
    _, school_id, student_id = auth
    return await portal_svc.get_my_profile(student_id, school_id, db)


@router.get("/children", response_model=list[PortalProfile])
async def list_my_children(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Guardian-only — the list of linked students a guardian can switch between."""
    user_id, school_id = ids
    user = await db.get(User, user_id)
    if not user or not user.is_active or user.guardian_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Portal access is limited to guardian accounts.")
    return await portal_svc.list_my_children(user.guardian_id, school_id, db)


@router.get("/term-enrollments", response_model=list[PortalTermEnrollmentRead])
async def list_my_term_enrollments(
    auth=Depends(_require_portal_access),
    db: AsyncSession = Depends(get_db),
):
    _, school_id, student_id = auth
    return await portal_svc.list_my_term_enrollments(student_id, school_id, db)


@router.post("/excuse-requests", response_model=ExcuseRequestRead, status_code=201)
async def submit_excuse_request(
    req: ExcuseRequestCreate,
    auth=Depends(_require_portal_access),
    db: AsyncSession = Depends(get_db),
):
    """Submit an absence excuse — a student for themselves, or a guardian
    for a verified linked child (?student_id=, checked by _require_portal_access)."""
    user_id, school_id, student_id = auth
    user = await db.get(User, user_id)
    return await excuse_svc.submit_excuse_request(
        student_id, user.guardian_id if user else None, user_id, req, school_id, db,
    )


@router.get("/excuse-requests", response_model=list[ExcuseRequestRead])
async def list_my_excuse_requests(
    auth=Depends(_require_portal_access),
    db: AsyncSession = Depends(get_db),
):
    _, school_id, student_id = auth
    return await excuse_svc.list_my_excuse_requests(student_id, school_id, db)


@router.get("/report-cards/{enrollment_id}")
async def portal_get_report_card(
    enrollment_id: uuid.UUID,
    auth=Depends(_require_portal_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the PDF report card for the logged-in student, or (for a guardian)
    the child named by ?student_id=.
    Returns 403 until the school publishes at least one assessment for the term.
    """
    user_id, school_id, student_id = auth

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

    context = await rc_svc.assemble(enrollment_id, school_id, user_id, db)
    # WeasyPrint is synchronous and CPU-heavy — off the event loop, or every
    # report card generated blocks every other concurrent request.
    pdf_bytes = await asyncio.to_thread(render_report_card, context)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="report_{context["admission_number"]}_{context["term_name"]}.pdf"'
            )
        },
    )
