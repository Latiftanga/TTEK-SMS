from __future__ import annotations
import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.redis import get_arq
from app.core.teacher_scope import classes_for_scope, resolve_report_card_scope, year_for_term
from app.models.academic import AcademicTerm, Class, SHSProgramme
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.schemas.academic import ClassRead
from app.schemas.assessments import BulkReportJobRead, BulkReportRequest
from app.schemas.behaviour import BehaviourRecordCreate, BehaviourRecordRead
from app.schemas.students import EnrollmentForReport
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
    auth=Depends(require_permission("assessments", "record_behaviour")),
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
    user_id, school_id = auth
    return await beh_svc.list_behaviour_records(student_id, term_id, school_id, user_id, db)


@router.delete("/behaviour/{record_id}", status_code=204)
async def delete_behaviour_record(
    record_id: uuid.UUID,
    override_reason: str | None = Query(None),
    auth=Depends(require_permission("assessments", "record_behaviour")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    await beh_svc.delete_behaviour_record(record_id, school_id, user_id, db, override_reason)


# ── Class enrollment list (for report card selection) ────────────────────────

@router.get("/report-cards/enrollments", response_model=list[EnrollmentForReport])
async def list_class_enrollments(
    class_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Return all term-enrolled students for a class+term, with their enrollment IDs."""
    user_id, school_id = auth
    year_id = await year_for_term(term_id, db)
    if year_id is not None:
        scope = await resolve_report_card_scope(user_id, year_id, db)
        if scope is not None and class_id not in scope:
            raise HTTPException(404, "Class not found.")
    rows = await db.execute(
        select(
            TermEnrollment.id,
            Student.id,
            Student.admission_number,
            Student.first_name,
            Student.last_name,
            Student.gender,
            StudentClassAssignment.class_id,
            Class.level,
            Class.year_group,
            Class.stream,
            SHSProgramme.name,
        )
        .join(Student, Student.id == TermEnrollment.student_id)
        .join(AcademicTerm, AcademicTerm.id == TermEnrollment.academic_term_id)
        .outerjoin(
            StudentClassAssignment,
            (StudentClassAssignment.student_id == TermEnrollment.student_id)
            & (StudentClassAssignment.academic_year_id == AcademicTerm.academic_year_id),
        )
        .outerjoin(Class, Class.id == StudentClassAssignment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(
            TermEnrollment.academic_term_id == term_id,
            TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
            StudentClassAssignment.class_id == class_id,
            StudentClassAssignment.is_active.is_(True),
        )
        .order_by(Student.last_name, Student.first_name)
    )
    result = []
    for row in rows:
        (enroll_id, stu_id, adm_no, first, last, gender,
         cls_id, level, yr_grp, stream, prog) = row
        parts = [str(p) for p in [level, yr_grp, prog, stream] if p]
        display_cls = " ".join(parts) if parts else None
        result.append(EnrollmentForReport(
            enrollment_id=enroll_id,
            student_id=stu_id,
            admission_number=adm_no,
            display_name=f"{first} {last}",
            gender=gender.value if gender else None,
            class_id=cls_id,
            class_display_name=display_cls,
        ))
    return result


# Registered before /report-cards/{enrollment_id} — a literal path segment
# would otherwise be swallowed by the UUID path param.
@router.get("/report-cards/my-classes", response_model=list[ClassRead])
async def list_my_report_classes(
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Classes the caller can view/generate report cards for — scoped to
    their own ClassTeacher assignment(s) unless they hold
    assessments.approve_scores."""
    user_id, school_id = auth
    year_id = await year_for_term(term_id, db)
    if year_id is None:
        return await classes_for_scope(None, school_id, db)
    scope = await resolve_report_card_scope(user_id, year_id, db)
    return await classes_for_scope(scope, school_id, db)


# ── Single report card ────────────────────────────────────────────────────────

@router.get("/report-cards/{enrollment_id}")
async def get_report_card(
    enrollment_id: uuid.UUID,
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
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


# ── Bulk report cards ─────────────────────────────────────────────────────────

@router.post("/report-cards/bulk", response_model=BulkReportJobRead, status_code=202)
async def queue_bulk_report(
    req: BulkReportRequest,
    auth=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    job_id = str(uuid.uuid4())
    arq = await get_arq()
    try:
        await arq.enqueue_job(
            "bulk_generate_report_cards",
            job_id=job_id,
            class_id=str(req.class_id),
            academic_term_id=str(req.academic_term_id),
            school_id=str(school_id),
            user_id=str(user_id),
            _job_id=job_id,
        )
    finally:
        await arq.aclose()
    return BulkReportJobRead(
        job_id=job_id,
        class_id=req.class_id,
        academic_term_id=req.academic_term_id,
        status="queued",
    )


@router.get("/report-cards/bulk/{job_id}/download")
async def download_bulk_report(
    job_id: str,
    auth=Depends(require_permission("assessments", "view")),
):
    # Path is built from the CALLER's own school_id, never a client-supplied
    # one — bulk_report_job.py writes into this same school-namespaced
    # directory, so a job_id belonging to another school (job_id alone gives
    # no ownership signal) resolves to a path that was never written here
    # and cleanly 404s instead of streaming a different school's report cards.
    _user_id, school_id = auth
    zip_path = Path(settings.local_upload_dir) / "bulk" / str(school_id) / f"{job_id}.zip"
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
