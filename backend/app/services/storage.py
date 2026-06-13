"""
File storage service — local disk now, Cloudflare R2 later.

All file I/O goes through this module so the rest of the codebase never
touches the filesystem directly.  When storage_backend switches to R2,
only this file changes.

LOGO STORAGE
------------
Logos are saved as WebP regardless of the upload format.  WebP is smaller
than PNG/JPEG, has >95% browser support, and allows us to use a single
deterministic filename per school:

    logos/{school_id}.webp

Re-uploading replaces the file in place — no orphan files accumulate.

LIMITS
------
MAX_LOGO_BYTES : 2 MB   — rejects oversized uploads before reading into memory
MAX_LOGO_PX    : 400 px — longest edge; Pillow downscales proportionally
ALLOWED_TYPES  : JPEG, PNG, WebP
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image

from app.core.config import settings

MAX_LOGO_BYTES = 2 * 1024 * 1024   # 2 MB
MAX_LOGO_PX = 400                   # longest edge in pixels
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _upload_root() -> Path:
    p = Path(settings.local_upload_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def save_logo(file: UploadFile, school_id: uuid.UUID) -> str:
    """
    Validate, resize, convert to WebP, and save a school logo.

    Returns the path relative to the upload root, e.g. ``logos/uuid.webp``.
    The caller stores this in school.logo_path.

    Raises:
        415  File is not JPEG, PNG, or WebP.
        413  File exceeds 2 MB.
        422  File content is not a valid image (even if content-type looked right).
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Logo must be JPEG, PNG, or WebP. Got: {file.content_type}",
        )

    raw = await file.read(MAX_LOGO_BYTES + 1)
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Logo must be 2 MB or smaller.",
        )

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        img = Image.open(io.BytesIO(raw))  # re-open after verify (verify closes the stream)
        img = img.convert("RGBA")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File could not be read as an image.",
        )

    if max(img.width, img.height) > MAX_LOGO_PX:
        img.thumbnail((MAX_LOGO_PX, MAX_LOGO_PX), Image.LANCZOS)

    logos_dir = _upload_root() / "logos"
    logos_dir.mkdir(exist_ok=True)

    dest = logos_dir / f"{school_id}.webp"
    img.save(dest, format="WEBP", quality=90)

    return f"logos/{school_id}.webp"
