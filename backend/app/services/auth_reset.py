"""
Password reset service.

FLOW
----
1. User calls POST /auth/forgot-password with their login identifier.
   forgot_password() finds the user, generates a secure reset token, and
   stores the SHA-256 hash in Redis with a 1-hour TTL.
   The raw token is returned so the caller can include it in an email/SMS.
   (In production, a background job should send the email — not done yet.)

   The response is always 204 regardless of whether the identifier exists,
   preventing user enumeration.

2. User clicks the link → frontend calls POST /auth/reset-password with
   the raw token and their new password.
   reset_password() looks up the hash in Redis, verifies it, updates the
   password, and deletes the key so the token cannot be reused.

STORAGE
-------
Reset tokens live in Redis, not the database:
  key:   pwd_reset:{sha256_hash}
  value: {user_id as string}
  TTL:   3600 seconds (1 hour)

This avoids a new DB table and auto-expires without a cleanup job.
If Redis is unavailable, password reset is temporarily disabled — a
reasonable trade-off for a school management system.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_password_reset_token,
    hash_password,
    hash_token,
    password_reset_expiry_seconds,
    verify_password,
)
from app.models.auth import LoginType, User
from app.models.school import School
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth import _find_user_by_identifier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_REDIS_KEY_PREFIX = "pwd_reset:"


async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncSession,
) -> str | None:
    """
    Generate a password reset token for the given identifier.

    Always returns without error — never reveals whether the identifier
    exists (prevents user enumeration).

    Returns:
        The raw reset token string if a user was found, else None.
        In production, None means "email will be sent if account exists".
    """
    from app.core.redis import redis_client
    from app.schemas.auth import LoginRequest

    # Reuse _find_user_by_identifier from the main auth service.
    # Build a minimal LoginRequest-compatible object.
    login_req = LoginRequest(
        login_type=req.login_type,
        identifier=req.identifier,
        school_code=req.school_code,
        password="",   # not checked here
    )

    try:
        user = await _find_user_by_identifier(login_req, db)
    except HTTPException:
        return None  # school_code invalid etc. — return silently

    if not user or not user.is_active:
        return None

    raw_token, token_hash = create_password_reset_token()

    if redis_client:
        key = f"{_REDIS_KEY_PREFIX}{token_hash}"
        await redis_client.setex(key, password_reset_expiry_seconds(), str(user.id))

    return raw_token


async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession,
) -> None:
    """
    Consume a reset token and update the user's password.

    The token is deleted from Redis immediately after verification so it
    cannot be reused even within the 1-hour TTL window.

    Raises:
        400  Token is invalid, expired, or already used.
        404  User referenced by the token no longer exists.
    """
    from app.core.redis import redis_client

    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is temporarily unavailable. Please try again later.",
        )

    token_hash = hash_token(req.token)
    key = f"{_REDIS_KEY_PREFIX}{token_hash}"

    user_id_str = await redis_client.get(key)
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid or has expired.",
        )

    user = await db.get(User, uuid.UUID(user_id_str))
    if not user:
        await redis_client.delete(key)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # Delete before updating — if the DB flush fails the token is gone,
    # but that's safer than leaving a reusable token around.
    await redis_client.delete(key)

    user.password_hash = hash_password(req.new_password)
    await db.flush()
