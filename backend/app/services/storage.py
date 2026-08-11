"""
File storage service — local disk now, Cloudflare R2 later.

All file I/O goes through this module so the rest of the codebase never
touches the filesystem directly.  When storage_backend switches to R2,
only this file changes.

IMAGE STORAGE (logos, student photos)
--------------------------------------
Images are saved as WebP regardless of the upload format. WebP is smaller
than PNG/JPEG, has >95% browser support, and allows us to use a single
deterministic filename per owner:

    logos/{school_id}.webp
    photos/{student_id}.webp
    staff-photos/{staff_id}.webp

Re-uploading replaces the file in place — no orphan files accumulate.

LIMITS
------
MAX_LOGO_BYTES  : 2 MB   — rejects oversized uploads before reading into memory
MAX_LOGO_PX     : 400 px — longest edge; Pillow downscales proportionally
MAX_PHOTO_BYTES : 3 MB
MAX_PHOTO_PX    : 600 px — longest edge
ALLOWED_TYPES   : JPEG, PNG, WebP
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image

from app.core.config import settings

MAX_LOGO_BYTES = 2 * 1024 * 1024    # 2 MB
MAX_LOGO_PX = 400                    # longest edge in pixels
MAX_PHOTO_BYTES = 3 * 1024 * 1024   # 3 MB
MAX_PHOTO_PX = 600                   # longest edge in pixels
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _upload_root() -> Path:
    p = Path(settings.local_upload_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _read_and_validate_image(file: UploadFile, max_bytes: int, max_px: int, label: str) -> Image.Image:
    """
    Validate content-type and size, decode, and downscale an uploaded image.

    Raises:
        415  File is not JPEG, PNG, or WebP.
        413  File exceeds max_bytes.
        422  File content is not a valid image (even if content-type looked right).
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"{label} must be JPEG, PNG, or WebP. Got: {file.content_type}",
        )

    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{label} must be {max_bytes // (1024 * 1024)} MB or smaller.",
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

    if max(img.width, img.height) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)

    return img


async def save_logo(file: UploadFile, school_id: uuid.UUID) -> str:
    """Validate, resize, convert to WebP, and save a school logo.

    Returns the path relative to the upload root, e.g. ``logos/uuid.webp``.
    The caller stores this in school.logo_path.
    """
    img = await _read_and_validate_image(file, MAX_LOGO_BYTES, MAX_LOGO_PX, "Logo")
    logos_dir = _upload_root() / "logos"
    logos_dir.mkdir(exist_ok=True)
    dest = logos_dir / f"{school_id}.webp"
    img.save(dest, format="WEBP", quality=90)
    return f"logos/{school_id}.webp"


async def save_student_photo(file: UploadFile, student_id: uuid.UUID) -> str:
    """Validate, resize, convert to WebP, and save a student profile photo.

    Returns the path relative to the upload root, e.g. ``photos/uuid.webp``.
    The caller stores this in student.photo_path.
    """
    img = await _read_and_validate_image(file, MAX_PHOTO_BYTES, MAX_PHOTO_PX, "Photo")
    photos_dir = _upload_root() / "photos"
    photos_dir.mkdir(exist_ok=True)
    dest = photos_dir / f"{student_id}.webp"
    img.save(dest, format="WEBP", quality=90)
    return f"photos/{student_id}.webp"


def delete_student_photo(student_id: uuid.UUID) -> None:
    """Remove a student's stored photo file, if any. Never raises if absent."""
    (_upload_root() / "photos" / f"{student_id}.webp").unlink(missing_ok=True)


async def save_staff_photo(file: UploadFile, staff_id: uuid.UUID) -> str:
    """Validate, resize, convert to WebP, and save a staff profile photo.

    Own subdirectory (not photos/, which is student-only) — same pipeline,
    kept separate so the two id spaces can never collide on disk.
    Returns the path relative to the upload root, e.g. ``staff-photos/uuid.webp``.
    The caller stores this in staff_member.photo_path.
    """
    img = await _read_and_validate_image(file, MAX_PHOTO_BYTES, MAX_PHOTO_PX, "Photo")
    staff_photos_dir = _upload_root() / "staff-photos"
    staff_photos_dir.mkdir(exist_ok=True)
    dest = staff_photos_dir / f"{staff_id}.webp"
    img.save(dest, format="WEBP", quality=90)
    return f"staff-photos/{staff_id}.webp"


def delete_staff_photo(staff_id: uuid.UUID) -> None:
    """Remove a staff member's stored photo file, if any. Never raises if absent."""
    (_upload_root() / "staff-photos" / f"{staff_id}.webp").unlink(missing_ok=True)
