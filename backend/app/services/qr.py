"""
QR token generation and verification for report cards.

Token format (URL-safe, opaque to the client):
    base64url( "{enrollment_id}|{school_id}" ) + "." + hmac_sha256[:16]

The verify endpoint is public — it decodes the token and returns basic
enrollment info without exposing scores.

Secret: settings.secret_key (same key as JWT; changing it invalidates all tokens).
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import io
import uuid

import qrcode
from fastapi import HTTPException

from app.core.config import settings


def _b64url(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).rstrip(b"=").decode()


def _b64url_decode(s: str) -> str:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding).decode()


def _sign(payload: str) -> str:
    return hmac.new(
        settings.hmac_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]


def generate_token(enrollment_id: uuid.UUID, school_id: uuid.UUID) -> str:
    payload = f"{enrollment_id}|{school_id}"
    sig = _sign(payload)
    return f"{_b64url(payload)}.{sig}"


def generate_qr_image(token: str) -> str:
    """Base64 PNG data URI of a QR code encoding the public verify URL for this token."""
    url = f"{settings.app_base_url}/verify/{token}"
    img = qrcode.make(url, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def verify_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (enrollment_id, school_id) or raises HTTP 404."""
    try:
        b64_part, sig = token.rsplit(".", 1)
        payload = _b64url_decode(b64_part)
        enrollment_str, school_str = payload.split("|")
    except Exception:
        raise HTTPException(404, "Invalid verification token.")
    if not hmac.compare_digest(sig, _sign(payload)):
        raise HTTPException(404, "Invalid verification token.")
    try:
        return uuid.UUID(enrollment_str), uuid.UUID(school_str)
    except ValueError:
        raise HTTPException(404, "Invalid verification token.")
