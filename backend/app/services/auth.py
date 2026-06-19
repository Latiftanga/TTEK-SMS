"""
Authentication service — the business logic for all auth flows.

This module handles identity verification, session lifecycle, and user
onboarding via invitations.  It does not deal with HTTP (no Request,
no JSONResponse) — that belongs in routers/auth.py.

FLOWS IMPLEMENTED
-----------------
login()             Verify credentials → issue access + refresh token pair
refresh()           Rotate refresh token → issue new token pair
logout()            Revoke refresh token
change_password()   Verify current password → store new hash
create_invitation() Generate an invitation link for a new staff member
accept_invitation() Convert an invitation into a real user account

SECURITY DECISIONS (important for future debugging)
-----------------------------------------------------
1. login() returns the SAME 401 whether the user does not exist or the
   password is wrong.  This prevents user enumeration — an attacker cannot
   probe which email addresses are registered by observing different errors.

2. Refresh token rotation: every call to refresh() immediately revokes the
   presented token and issues a completely new one.  If the same refresh token
   is used twice (e.g. network retry), the second call returns 401.
   This detects token theft: if a token is stolen and used, the legitimate
   owner's next refresh attempt will fail, alerting them to the compromise.

3. Passwords are hashed with bcrypt (see core/auth.py).  The plaintext
   password is never logged or stored anywhere.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    refresh_token_expiry,
    verify_password,
)
from app.core.config import settings
from app.models.auth import LoginType, User, UserSession
from app.models.school import School
from app.schemas.auth import LoginRequest, TokenResponse


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Login ─────────────────────────────────────────────────────────────────────

async def login(
    req: LoginRequest,
    db: AsyncSession,
    ip: str | None = None,
) -> TokenResponse:
    """
    Authenticate a user and return a new token pair.

    The login identifier depends on login_type:
      EMAIL        → req.identifier is the user's email (case-insensitive)
      PHONE        → req.identifier is the user's phone number
      ADMISSION_ID → req.identifier is the student's admission number;
                     req.school_code is required to scope the lookup to a school

    Side effects:
      - Creates a new UserSession row (stores hashed refresh token + IP).
      - Updates user.last_login_at.

    Returns:
        TokenResponse with access_token, refresh_token, and expires_in seconds.

    Raises:
        400  ADMISSION_ID login attempted without providing school_code
        401  Credentials are wrong (same error whether user exists or not)
        403  User account exists but has been deactivated
    """
    user = await _find_user_by_identifier(req, db)

    # Intentionally combine "user not found" and "wrong password" into one error.
    # This prevents an attacker from enumerating which identifiers are registered.
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    # Check active status separately AFTER password verification to avoid
    # leaking whether a deactivated account exists.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    raw_refresh, refresh_hash = create_refresh_token()
    expires_at = (
        _utcnow() + timedelta(days=30) if req.remember_me
        else refresh_token_expiry()
    )
    session = UserSession(
        user_id=user.id,
        school_id=user.school_id,
        refresh_token_hash=refresh_hash,
        ip_address=ip,
        created_at=_utcnow(),
        expires_at=expires_at,
    )
    db.add(session)
    user.last_login_at = _utcnow()
    await db.flush()

    access_token = create_access_token(user.id, user.school_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


async def _find_user_by_identifier(req: LoginRequest, db: AsyncSession) -> User | None:
    """
    Locate a user by the appropriate identifier based on login_type.

    Returns None if no matching user exists (caller decides what error to raise).
    """
    if req.login_type == LoginType.EMAIL:
        return await db.scalar(
            select(User).where(User.email == req.identifier.lower().strip())
        )

    if req.login_type == LoginType.PHONE:
        return await db.scalar(
            select(User).where(User.phone == req.identifier.strip())
        )

    # ADMISSION_ID: must first resolve the school to scope the lookup.
    if not req.school_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="school_code is required when login_type is ADMISSION_ID.",
        )

    school = await db.scalar(
        select(School).where(School.school_code == req.school_code.upper())
    )
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School with code '{req.school_code.upper()}' not found.",
        )

    return await db.scalar(
        select(User).where(
            User.school_id == school.id,
            User.admission_id == req.identifier.strip(),
            User.login_type == LoginType.ADMISSION_ID,
        )
    )


# ── Refresh ───────────────────────────────────────────────────────────────────

async def refresh(raw_token: str, db: AsyncSession) -> TokenResponse:
    """
    Rotate a refresh token and return a new token pair.

    Token rotation means:
      - The presented token is immediately revoked (revoked_at is stamped).
      - A brand-new refresh token is created.
      - The new access token is signed with fresh expiry.

    If the same refresh token is submitted twice (e.g. due to a network
    retry or token theft), the second call returns 401.

    Raises:
        401  Token not found, already revoked, expired, or user is deactivated.
    """
    token_hash = hash_token(raw_token)

    session = await db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has already been used.",
        )

    if session.expires_at < _utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )

    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or has been deactivated.",
        )

    # Revoke the old session and create a new one atomically.
    session.revoked_at = _utcnow()

    raw_new, hash_new = create_refresh_token()
    new_session = UserSession(
        user_id=user.id,
        school_id=user.school_id,
        refresh_token_hash=hash_new,
        ip_address=session.ip_address,
        created_at=_utcnow(),
        expires_at=refresh_token_expiry(),
    )
    db.add(new_session)
    await db.flush()

    access_token = create_access_token(user.id, user.school_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_new,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


# ── Logout ────────────────────────────────────────────────────────────────────

async def logout(raw_token: str, db: AsyncSession) -> None:
    """
    Revoke the refresh token, ending the session.

    The access token cannot be revoked (it's stateless); it will continue to
    work until it expires (max 15 minutes).  For immediate revocation, reduce
    jwt_access_token_expire_minutes in settings.

    This function is intentionally silent if the token is not found or is
    already revoked.  Double-logout is not an error.
    """
    token_hash = hash_token(raw_token)
    session = await db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    )
    if session:
        session.revoked_at = _utcnow()


# ── Change password ───────────────────────────────────────────────────────────

async def change_password(
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
    db: AsyncSession,
) -> None:
    """
    Verify the current password and replace it with a new bcrypt hash.

    Does NOT revoke existing sessions — the user stays logged in on all
    devices.  If you want "log out everywhere on password change", call
    revoke_all_sessions() before this (not yet implemented).

    Raises:
        400  current_password does not match the stored hash.
        404  user_id not found (should not happen in normal operation).
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    user.password_hash = hash_password(new_password)
    await db.flush()


