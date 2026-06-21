"""
ARQ job: bulk_generate_report_cards

Generates one PDF per student in a class for a given term, zips them,
and writes the ZIP to /uploads/bulk/{job_id}.zip.

The API router queues this job and returns the job_id.
The download endpoint streams the ZIP once it exists.
"""
from __future__ import annotations
import io
import uuid
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.academic import AcademicTerm
from app.models.students import StudentClassAssignment, TermEnrollment
from app.services.pdf import render_report_card
from app.services.report_card import assemble


async def bulk_generate_report_cards(
    ctx: dict,
    job_id: str,
    class_id: str,
    academic_term_id: str,
    school_id: str,
    format: str,
) -> dict:
    """ARQ job — runs in the worker process."""
    AsyncSessionLocal = ctx["db"]
    async with AsyncSessionLocal() as db:
        return await _run(
            db,
            job_id=job_id,
            class_id=uuid.UUID(class_id),
            academic_term_id=uuid.UUID(academic_term_id),
            school_id=uuid.UUID(school_id),
            format=format,
        )


async def _run(
    db: AsyncSession,
    job_id: str,
    class_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    format: str,
) -> dict:
    term = await db.get(AcademicTerm, academic_term_id)
    enrollments = (await db.scalars(
        select(TermEnrollment)
        .join(
            StudentClassAssignment,
            (StudentClassAssignment.student_id == TermEnrollment.student_id)
            & (StudentClassAssignment.academic_year_id == term.academic_year_id)
            & (StudentClassAssignment.class_id == class_id),
        )
        .where(
            TermEnrollment.academic_term_id == academic_term_id,
            TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
        )
    )).all()

    zip_buffer = io.BytesIO()
    generated = failed = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for te in enrollments:
            try:
                context = await assemble(te.id, school_id, format, db)
                pdf_bytes = render_report_card(context, format)
                filename = f"{context['admission_number']}_{context['student_name'].replace(' ', '_')}.pdf"
                zf.writestr(filename, pdf_bytes)
                generated += 1
            except Exception as exc:
                zf.writestr(f"error_{te.student_id}.txt", str(exc))
                failed += 1

    bulk_dir = Path(settings.local_upload_dir) / "bulk"
    bulk_dir.mkdir(parents=True, exist_ok=True)
    zip_path = bulk_dir / f"{job_id}.zip"
    zip_path.write_bytes(zip_buffer.getvalue())

    return {"job_id": job_id, "generated": generated, "failed": failed}
