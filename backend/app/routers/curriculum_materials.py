"""
Curriculum material upload/list/delete router — admin/HEAD tier, reusing the
existing documents.manage/documents.view permissions (see
services/curriculum_materials.py for why this isn't just another
DocumentRecord entity_type).

Upload enqueues a background ARQ text-extraction job (services/
curriculum_extraction.py) — a real textbook is too slow to process inline.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.redis import get_arq
from app.schemas.curriculum_materials import CurriculumMaterialRead
from app.services import curriculum_materials as cm_svc
from app.services.curriculum_materials import MAX_FILE_BYTES

router = APIRouter(prefix="/curriculum-materials", tags=["curriculum-materials"])

_CONTENT_LENGTH_SLOP = 64 * 1024


@router.post("/{class_subject_id}", response_model=CurriculumMaterialRead, status_code=201)
async def upload_material(
    request: Request,
    class_subject_id: uuid.UUID,
    document_type: str = Query(...),
    file: UploadFile = File(...),
    auth=Depends(require_permission("documents", "manage")),
    db: AsyncSession = Depends(get_db),
):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_FILE_BYTES + _CONTENT_LENGTH_SLOP:
        raise HTTPException(413, "File exceeds 50 MB limit.")
    user_id, school_id = auth
    material = await cm_svc.upload_material(class_subject_id, document_type, file, school_id, user_id, db)

    arq = await get_arq()
    try:
        await arq.enqueue_job("extract_curriculum_material", material_id=str(material.id))
    finally:
        await arq.aclose()

    return material


@router.get("/{class_subject_id}", response_model=list[CurriculumMaterialRead])
async def list_materials(
    class_subject_id: uuid.UUID,
    auth=Depends(require_permission("documents", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await cm_svc.list_materials(class_subject_id, school_id, db)


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: uuid.UUID,
    auth=Depends(require_permission("documents", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    await cm_svc.delete_material(material_id, school_id, db)
