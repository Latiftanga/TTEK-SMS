"""
Password reset via SMS OTP.

FLOW
----
1. POST /auth/forgot-password
   Looks up the user by identifier, generates a 6-digit OTP, stores it in
   Redis (TTL 10 min), and sends it via the school's active SMS driver.
   Always returns 204 — never reveals whether the account exists.

2. POST /auth/verify-otp
   Validates the OTP. On success, deletes it and issues a short-lived
   opaque reset token (stored as a hash in Redis, same mechanism as before).
   Enforces a maximum of 5 wrong attempts per OTP before invalidation.
   Returns the raw reset token so the frontend can proceed to step 3.

3. POST /auth/reset-password
   Consumes the reset token (validates hash, deletes key) and sets the
   new password. Token is single-use and expires in 10 minutes.

STORAGE
-------
OTP:          otp:reset:{user_id}        → JSON {otp, attempts}    TTL 600s
Reset token:  pwd_reset:{sha256(token)}  → user_id as string       TTL 600s

Redis is the only store — no new DB tables needed.
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_password_reset_token,
    hash_password,
    hash_token,
)
from app.models.auth import User
from app.models.school import SmsConfig
from app.models.staff import StaffMember
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest, VerifyOtpRequest
from app.services.auth import _find_user_by_identifier
from app.services.sms_driver import build_driver


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_OTP_PREFIX   = "otp:reset:"
_RESET_PREFIX = "pwd_reset:"
_OTP_TTL      = 600   # 10 minutes
_RESET_TTL    = 600   # 10 minutes (same window to complete reset)
_MAX_ATTEMPTS = 5


def _otp_key(user_id: uuid.UUID) -> str:
    return f"{_OTP_PREFIX}{user_id}"


def _reset_key(token_hash: str) -> str:
    return f"{_RESET_PREFIX}{token_hash}"


async def _get_school_driver(school_id: uuid.UUID, db: AsyncSession):
    """Return the active SMS driver for a school, or None if not configured."""
    from sqlalchemy import select
    config = await db.scalar(
        select(SmsConfig).where(
            SmsConfig.school_id == school_id,
            SmsConfig.is_active.is_(True),
        )
    )
    if not config:
        return None
    return build_driver(config.provider, config.api_key, config.api_secret, config.sender_id)


async def _resolve_phone(user: User, db: AsyncSession) -> str | None:
    """Prefer StaffMember.phone; fall back to User.phone (set on PHONE-type accounts)."""
    if user.staff_member_id:
        staff = await db.get(StaffMember, user.staff_member_id)
        if staff and staff.phone:
            return staff.phone
    return user.phone


async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession) -> str | None:
    """
    Generate and send a 6-digit OTP to the user's registered phone.

    Returns the OTP string (for dev-mode response body), or None.
    Always returns without error — never reveals whether the account exists.
    """
    from app.core.redis import redis_client
    from app.schemas.auth import LoginRequest

    login_req = LoginRequest(
        login_type=req.login_type,
        identifier=req.identifier,
        school_code=req.school_code,
        password="",
    )

    try:
        user = await _find_user_by_identifier(login_req, db)
    except HTTPException:
        return None

    if not user or not user.is_active:
        return None

    phone = await _resolve_phone(user, db)
    if not phone:
        return None  # no phone to send to — silently skip

    otp = f"{secrets.randbelow(1_000_000):06d}"

    if redis_client:
        await redis_client.setex(
            _otp_key(user.id),
            _OTP_TTL,
            json.dumps({"otp": otp, "attempts": 0}),
        )

    # Send SMS (fire-and-forget — never crashes the endpoint)
    if redis_client and user.school_id:
        try:
            driver = await _get_school_driver(user.school_id, db)
            if driver:
                msg = (
                    f"TTEK-SMS: Your password reset code is {otp}. "
                    f"Valid for 10 minutes. Do not share this code."
                )
                await driver.send(phone, msg)
        except Exception:
            pass  # OTP is in Redis — user can still get it another way in dev

    return otp  # caller decides whether to expose this (dev only)


async def verify_otp(req: VerifyOtpRequest, db: AsyncSession) -> str:
    """
    Validate a 6-digit OTP and return a short-lived reset token.

    The reset token is what the frontend passes to /auth/reset-password.
    Enforces max 5 wrong attempts before invalidating the OTP.

    Raises:
        400  OTP invalid or expired.
        429  Too many wrong attempts — OTP has been invalidated.
    """
    from app.core.redis import redis_client
    from app.schemas.auth import LoginRequest

    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is temporarily unavailable. Please try again later.",
        )

    login_req = LoginRequest(
        login_type=req.login_type,
        identifier=req.identifier,
        school_code=req.school_code,
        password="",
    )

    try:
        user = await _find_user_by_identifier(login_req, db)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid or expired code.")

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid or expired code.")

    key = _otp_key(user.id)
    raw = await redis_client.get(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code has expired. Please request a new one.",
        )

    data = json.loads(raw)
    if data["attempts"] >= _MAX_ATTEMPTS:
        await redis_client.delete(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    if data["otp"] != req.otp:
        data["attempts"] += 1
        # Preserve remaining TTL
        remaining_ttl = await redis_client.ttl(key)
        await redis_client.setex(key, max(int(remaining_ttl), 1), json.dumps(data))
        left = _MAX_ATTEMPTS - data["attempts"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect code. {left} attempt{'s' if left != 1 else ''} remaining.",
        )

    # Correct — delete OTP and issue a short-lived reset token
    await redis_client.delete(key)
    raw_token, token_hash = create_password_reset_token()
    await redis_client.setex(_reset_key(token_hash), _RESET_TTL, str(user.id))
    return raw_token


async def reset_password(req: ResetPasswordRequest, db: AsyncSession) -> None:
    """
    Consume a reset token and update the user's password.

    The token is single-use and is deleted before the password is written.
    This is the safest ordering — if the DB flush fails, the token is gone
    (forcing a new reset request) rather than leaving a reusable token.

    Raises:
        400  Token invalid, expired, or already used.
        404  User referenced by token no longer exists.
    """
    from app.core.redis import redis_client

    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is temporarily unavailable. Please try again later.",
        )

    token_hash = hash_token(req.token)
    key = _reset_key(token_hash)

    user_id_str = await redis_client.get(key)
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset session is invalid or has expired. Please start over.",
        )

    user = await db.get(User, uuid.UUID(user_id_str))
    if not user:
        await redis_client.delete(key)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await redis_client.delete(key)
    user.password_hash = hash_password(req.new_password)
    await db.flush()


async def update_profile(
    user_id: uuid.UUID,
    phone: str | None,
    address: str | None,
    db: AsyncSession,
) -> StaffMember:
    """Update a user's own editable staff profile fields (phone, address)."""
    user = await db.get(User, user_id)
    if not user or not user.staff_member_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found for this account.",
        )
    staff = await db.get(StaffMember, user.staff_member_id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff record not found.")

    if phone is not None:
        staff.phone = phone.strip() or None
    if address is not None:
        staff.address = address.strip() or None

    await db.flush()
    return staff
