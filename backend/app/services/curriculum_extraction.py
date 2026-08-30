"""
ARQ job: extract_curriculum_material

Extracts text per page from a real, already-uploaded CurriculumMaterial PDF
(pypdf — plain text extraction, not OCR; per the confirmed assumption these
are typed/exported documents, not scanned images) and writes one
CurriculumMaterialChunk per page with usable text, search_vector populated
via to_tsvector() at insert time for services/curriculum_search.py.

If zero pages yield usable text, extraction_status is set to EMPTY with a
clear extraction_error — surfaced to the admin in the upload UI, not
silently left looking like it worked (the scanned-PDF case).

Mirrors services/bulk_report_job.py's ARQ entrypoint/_run() split.
"""
from __future__ import annotations
import uuid
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, insert, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.curriculum_materials import CurriculumMaterial, CurriculumMaterialChunk, ExtractionStatus

# A page with fewer than this many non-whitespace characters is treated as
# "nothing usable" (a blank page, a page that's pure image/diagram, ...) —
# doesn't by itself flip the whole document to EMPTY, only affects whether
# THIS page gets its own chunk row.
_MIN_USABLE_CHARS = 20


async def extract_curriculum_material(ctx: dict, material_id: str) -> dict:
    """ARQ job — runs in the worker process."""
    AsyncSessionLocal = ctx["db"]
    async with AsyncSessionLocal() as db:
        result = await _run(db, uuid.UUID(material_id))
        await db.commit()
        return result


async def _run(db: AsyncSession, material_id: uuid.UUID) -> dict:
    mat = await db.get(CurriculumMaterial, material_id)
    if not mat:
        # A deleted/bogus id must not crash the worker.
        return {"material_id": str(material_id), "status": "not_found", "pages_extracted": 0}

    file_path = Path(settings.secure_upload_dir) / mat.file_path
    try:
        reader = PdfReader(str(file_path))
        pages_text = [(i + 1, (page.extract_text() or "")) for i, page in enumerate(reader.pages)]
    except Exception as exc:
        mat.extraction_status = ExtractionStatus.FAILED
        mat.extraction_error = f"Could not read this PDF: {exc}"
        await db.flush()
        return {"material_id": str(material_id), "status": "failed", "pages_extracted": 0}

    # Clear any prior chunks first — a re-run (e.g. after a corrected upload)
    # must not accumulate stale rows alongside fresh ones.
    await db.execute(delete(CurriculumMaterialChunk).where(CurriculumMaterialChunk.material_id == material_id))

    usable_pages = [(n, t.strip()) for n, t in pages_text if len(t.strip()) >= _MIN_USABLE_CHARS]
    if not usable_pages:
        mat.extraction_status = ExtractionStatus.EMPTY
        mat.extraction_error = (
            "No extractable text found in this PDF — this looks like a scanned "
            "document. Re-upload a text-based PDF (exported from Word or similar) "
            "for the AI assistant to use it."
        )
        await db.flush()
        return {"material_id": str(material_id), "status": "empty", "pages_extracted": 0}

    for page_number, text in usable_pages:
        await db.execute(
            insert(CurriculumMaterialChunk).values(
                id=uuid.uuid4(),
                school_id=mat.school_id,
                material_id=mat.id,
                page_number=page_number,
                chunk_text=text,
                search_vector=func.to_tsvector("english", text),
            )
        )

    mat.extraction_status = ExtractionStatus.DONE
    mat.extraction_error = None
    await db.flush()
    return {"material_id": str(material_id), "status": "done", "pages_extracted": len(usable_pages)}
