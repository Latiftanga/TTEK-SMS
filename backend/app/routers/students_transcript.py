"""GET /students/{student_id}/transcript — full multi-term academic history.

Not gated by graduation status: any student (active, withdrawn, transferred,
or graduated) can have their transcript pulled — this covers every term
they've been enrolled in so far, not just a graduated student's final record.

Permission is assessments.view (matching report_cards.py), not students.view —
this exposes score data, same bar as pulling a single report card.
"""
from __future__ import annotations
import asyncio
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.services import transcript as transcript_svc
from app.services.pdf import render_transcript

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}/transcript")
async def get_transcript(
    student_id: uuid.UUID,
    auth=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    context = await transcript_svc.assemble_transcript(student_id, school_id, db)
    # WeasyPrint is synchronous and CPU-heavy — off the event loop, matching
    # every other report-card render site.
    pdf_bytes = await asyncio.to_thread(render_transcript, context)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="transcript_{context["admission_number"]}.pdf"'
        },
    )
