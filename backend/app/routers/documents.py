from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.documents import DocumentRecordRead
from app.services import documents as doc_svc
from app.services.documents import MAX_FILE_BYTES

router = APIRouter(prefix="/documents", tags=["documents"])

# Slop above MAX_FILE_BYTES for multipart boundary/header overhead — this is
# a Content-Length pre-check, rejecting an obviously-oversized declared body
# before Starlette's multipart parser ever buffers it (memory/disk exhaustion
# from a huge upload otherwise isn't caught until well after the fact, since
# upload_document()'s own MAX_FILE_BYTES check only runs after the parser has
# already received the whole thing). Doesn't stop a client that lies about
# Content-Length or omits it — the reverse proxy in front of this in
# production enforces a hard cap on the wire regardless (see Caddyfile).
_CONTENT_LENGTH_SLOP = 64 * 1024


@router.post("/{entity_type}/{entity_id}", response_model=DocumentRecordRead, status_code=201)
async def upload_document(
    request: Request,
    entity_type: str,
    entity_id: uuid.UUID,
    document_type: str = Query(...),
    file: UploadFile = File(...),
    auth=Depends(require_permission("documents", "manage")),
    db: AsyncSession = Depends(get_db),
):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_FILE_BYTES + _CONTENT_LENGTH_SLOP:
        raise HTTPException(413, "File exceeds 10 MB limit.")
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
    full_path = Path(settings.secure_upload_dir) / rec.file_path
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
