from __future__ import annotations
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.redis import get_arq
from app.models.students import TermEnrollment
from app.schemas.assessments import (
    BehaviourRecordCreate, BehaviourRecordRead,
    BulkReportJobRead, BulkReportRequest,
)
from app.services import behaviour as beh_svc
from app.services import report_card as rc_svc
from app.services.pdf import render_report_card
from app.services.qr import verify_token
from app.core.config import settings

router = APIRouter(tags=["report-cards"])


# ── Behaviour records ─────────────────────────────────────────────────────────

@router.post("/behaviour", response_model=BehaviourRecordRead, status_code=201)
async def create_behaviour_record(
    req: BehaviourRecordCreate,
    auth=Depends(require_permission("assessments", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await beh_svc.create_behaviour_record(req, school_id, user_id, db)


@router.get("/behaviour", response_model=list[BehaviourRecordRead])
async def list_behaviour_records(
    student_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await beh_svc.list_behaviour_records(student_id, term_id, school_id, db)


@router.delete("/behaviour/{record_id}", status_code=204)
async def delete_behaviour_record(
    record_id: uuid.UUID,
    auth=Depends(require_permission("assessments", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    await beh_svc.delete_behaviour_record(record_id, school_id, db)


# ── Single report card ────────────────────────────────────────────────────────

@router.get("/report-cards/{enrollment_id}")
async def get_report_card(
    enrollment_id: uuid.UUID,
    format: str = Query("BASIC", pattern="^(BASIC|SHS|ECM)$"),
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
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


# ── Bulk report cards ─────────────────────────────────────────────────────────

@router.post("/report-cards/bulk", response_model=BulkReportJobRead, status_code=202)
async def queue_bulk_report(
    req: BulkReportRequest,
    auth=Depends(require_permission("assessments", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    job_id = str(uuid.uuid4())
    arq = await get_arq()
    try:
        await arq.enqueue_job(
            "bulk_generate_report_cards",
            job_id=job_id,
            class_id=str(req.class_id),
            academic_term_id=str(req.academic_term_id),
            school_id=str(school_id),
            format=req.format,
            _job_id=job_id,
        )
    finally:
        await arq.aclose()
    return BulkReportJobRead(
        job_id=job_id,
        class_id=req.class_id,
        academic_term_id=req.academic_term_id,
        format=req.format,
        status="queued",
    )


@router.get("/report-cards/bulk/{job_id}/download")
async def download_bulk_report(
    job_id: str,
    auth=Depends(require_permission("assessments", "view")),
):
    zip_path = Path(settings.local_upload_dir) / "bulk" / f"{job_id}.zip"
    if not zip_path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Bulk report not ready or job ID not found.")

    def _iter():
        with open(zip_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="reports_{job_id}.zip"'},
    )


# ── QR verification (public — no auth) ───────────────────────────────────────

@router.get("/verify/{token}")
async def verify_report_card(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    enrollment_id, school_id = verify_token(token)
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    te = await db.scalar(
        select(TermEnrollment)
        .where(TermEnrollment.id == enrollment_id, TermEnrollment.school_id == school_id)
        .options(selectinload(TermEnrollment.student))
    )
    if not te:
        from fastapi import HTTPException
        raise HTTPException(404, "Report card not found.")
    return {
        "valid": True,
        "student_name": f"{te.student.first_name} {te.student.last_name}",
        "admission_number": te.student.admission_number,
        "enrollment_id": str(enrollment_id),
    }
