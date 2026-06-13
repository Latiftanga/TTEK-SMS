"""
JWT token management and password hashing utilities.

This module contains only pure functions — no DB access, no HTTP concerns.
It is imported by services and by core/dependencies.py.

TOKEN TYPES
-----------
Access token (JWT, short-lived — 15 min by default)
    - Signed with app_secret_key using HS256.
    - Carries user_id and school_id as claims.
    - Stateless: the server does not store it.  Revoking requires waiting
      for expiry.  This is intentional — it keeps auth fast.
    - payload fields: sub (user_id), school_id, exp, iat, type="access"

Refresh token (opaque random string, long-lived — 7 days by default)
    - Generated with secrets.token_urlsafe(64) — cryptographically random.
    - NEVER stored in plaintext.  The SHA-256 hash is stored in user_session.
    - Rotated on every use: the old token is revoked and a new one is issued.
    - If an already-revoked token is presented, the server rejects it.

Invitation token
    - Same generation mechanism as refresh tokens (random + hashed).
    - Stored hashed in user_invitation.  Expires after 72 hours by default.

PASSWORD HASHING
----------------
Uses bcrypt (cost factor from bcrypt.gensalt() default = 12 rounds).
Input passwords are encoded to bytes before hashing.
verify_password() uses constant-time comparison to prevent timing attacks.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    The returned string is safe to store in the database.
    It includes the salt and cost factor, so no separate salt storage is needed.
    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """
    Check whether a plaintext password matches a bcrypt hash.

    Uses constant-time comparison internally (bcrypt.checkpw) to resist
    timing-based side-channel attacks.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Internal helpers ──────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ── Access token ──────────────────────────────────────────────────────────────

def create_access_token(user_id: uuid.UUID, school_id: uuid.UUID | None) -> str:
    """
    Create a signed JWT access token for the given user.

    The token expires in settings.jwt_access_token_expire_minutes minutes.
    school_id may be None for superadmin users who are not school-scoped.
    """
    expire = _utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "school_id": str(school_id) if school_id else None,
        "exp": expire,
        "iat": _utcnow(),
        "type": "access",  # guards against using a refresh token as an access token
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


class TokenPayload:
    """The decoded claims extracted from a validated access token."""

    def __init__(self, user_id: uuid.UUID, school_id: uuid.UUID | None) -> None:
        self.user_id = user_id
        self.school_id = school_id


def decode_access_token(token: str) -> TokenPayload:
    """
    Validate and decode a JWT access token.

    Raises:
        jose.JWTError  if the signature is invalid, the token is expired,
                       or the "type" claim is not "access".
    """
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])

    if payload.get("type") != "access":
        raise JWTError("Expected an access token but received a different token type.")

    user_id = uuid.UUID(payload["sub"])
    raw_school = payload.get("school_id")
    school_id = uuid.UUID(raw_school) if raw_school else None

    return TokenPayload(user_id=user_id, school_id=school_id)


# ── Refresh token ─────────────────────────────────────────────────────────────

def create_refresh_token() -> tuple[str, str]:
    """
    Generate a new refresh token pair.

    Returns:
        (raw_token, sha256_hash)
        - raw_token  is sent to the client and never stored server-side.
        - sha256_hash is stored in user_session.refresh_token_hash.
    """
    raw = secrets.token_urlsafe(64)
    hashed = _sha256(raw)
    return raw, hashed


def hash_token(raw: str) -> str:
    """
    Hash a raw token string for database lookup.

    Used when verifying an incoming refresh or invitation token: hash the
    client-supplied value and look up that hash in the database.
    """
    return _sha256(raw)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ── Invitation token ──────────────────────────────────────────────────────────

def create_invitation_token() -> tuple[str, str]:
    """
    Generate a new invitation token pair.

    Invitation tokens use the same generation mechanism as refresh tokens
    (random opaque string + SHA-256 hash for storage).

    Returns:
        (raw_token, sha256_hash) — same convention as create_refresh_token().
    """
    return create_refresh_token()


# ── Expiry helpers ────────────────────────────────────────────────────────────

def refresh_token_expiry() -> datetime:
    """Return the expiry datetime for a new refresh token."""
    return _utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)


def invitation_expiry(hours: int = 72) -> datetime:
    """Return the expiry datetime for a new invitation token."""
    return _utcnow() + timedelta(hours=hours)


def create_password_reset_token() -> tuple[str, str]:
    """
    Generate a password reset token pair.

    Same mechanism as invitation tokens — opaque random string + SHA-256 hash.
    The raw token is sent to the user (email/SMS); only the hash is stored
    in Redis with a 1-hour TTL.

    Returns:
        (raw_token, sha256_hash)
    """
    return create_refresh_token()


def password_reset_expiry_seconds() -> int:
    """TTL in seconds for a password reset token stored in Redis."""
    return 3600  # 1 hour
