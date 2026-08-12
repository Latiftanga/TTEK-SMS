from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.documents import DocumentRecordRead
from app.services import documents as doc_svc

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{entity_type}/{entity_id}", response_model=DocumentRecordRead, status_code=201)
async def upload_document(
    entity_type: str,
    entity_id: uuid.UUID,
    document_type: str = Query(...),
    file: UploadFile = File(...),
    auth=Depends(require_permission("documents", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await doc_svc.upload_document(
        entity_type, entity_id, document_type, file, school_id, user_id, db
    )


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: uuid.UUID,
    auth=Depends(require_permission("documents", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    rec = await doc_svc.get_document(doc_id, school_id, user_id, db, action="view")
    from pathlib import Path
    full_path = Path(settings.local_upload_dir) / rec.file_path
    if not full_path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "File not found on disk.")
    return FileResponse(
        path=str(full_path),
        filename=rec.file_name,
        media_type=rec.mime_type or "application/octet-stream",
    )


@router.get("/{entity_type}/{entity_id}", response_model=list[DocumentRecordRead])
async def list_documents(
    entity_type: str,
    entity_id: uuid.UUID,
    auth=Depends(require_permission("documents", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await doc_svc.list_documents(entity_type, entity_id, school_id, user_id, db)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    auth=Depends(require_permission("documents", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    await doc_svc.delete_document(doc_id, school_id, user_id, db)
