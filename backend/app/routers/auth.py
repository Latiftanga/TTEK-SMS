"""
Auth router — HTTP endpoints for the authentication and identity flows.

This file is intentionally thin.  Its only jobs are:
  1. Declare the HTTP routes (method, path, status code, response shape).
  2. Extract request data and pass it to the service layer.
  3. Format the service result into an HTTP response.

All business logic lives in services/auth.py.
All access control lives in core/dependencies.py.

ENDPOINTS
---------
POST /auth/login            Authenticate and receive a token pair
POST /auth/refresh          Rotate the refresh token
POST /auth/logout           Revoke the refresh token
GET  /auth/me               Return the current user's profile
POST /auth/change-password  Update password (requires current password)
POST /auth/invite           Send an invitation to a new staff member
POST /auth/accept-invite    Redeem an invitation and create an account
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth, require_permission
from app.models.auth import User
from app.schemas.auth import (
    AcceptInvitationRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InvitationCreate,
    InvitationInfo,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserRead,
)
from app.services import auth as auth_svc
from app.services import auth_invite as invite_svc
from app.services import auth_reset as reset_svc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate a user and return an access + refresh token pair.

    The client IP is captured for session audit logging.
    See services/auth.py → login() for the full flow and security notes.
    """
    ip = request.client.host if request.client else None
    return await auth_svc.login(req, db, ip=ip)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate the refresh token and return a new token pair.

    The submitted refresh_token is immediately revoked.  A brand-new
    refresh_token is returned.  Do not reuse the old one.
    """
    return await auth_svc.refresh(req.refresh_token, db)


@router.post("/logout", status_code=204)
async def logout(
    req: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke the refresh token, ending the session.

    The access token remains valid until it expires (≤15 min).
    Returns 204 whether or not the token was found.
    """
    await auth_svc.logout(req.refresh_token, db)


@router.get("/me", response_model=UserRead)
async def get_current_user(
    ids: tuple[uuid.UUID, uuid.UUID | None] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated user."""
    from sqlalchemy import select
    from app.models.staff import StaffMember

    user_id, _ = ids
    user = await db.get(User, user_id)
    result = UserRead.model_validate(user)

    if user.staff_member_id:
        staff = await db.get(StaffMember, user.staff_member_id)
        if staff:
            result.display_name = f"{staff.first_name} {staff.last_name}"
    elif user.is_superadmin:
        result.display_name = "Platform Admin"

    return result


@router.post("/change-password", status_code=204)
async def change_password(
    req: ChangePasswordRequest,
    ids: tuple[uuid.UUID, uuid.UUID | None] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Change the authenticated user's password.

    Requires the current password for verification.  Returns 204 on success.
    """
    user_id, _ = ids
    await auth_svc.change_password(user_id, req.current_password, req.new_password, db)


@router.post("/invite", status_code=201)
async def invite_staff(
    req: InvitationCreate,
    ids: tuple[uuid.UUID, uuid.UUID | None] = Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an invitation token for a new staff member.

    Requires the 'school.manage_users' permission.
    The returned token should be sent to the invitee via email or SMS.
    """
    user_id, school_id = ids
    raw_token = await invite_svc.create_invitation(
        req,
        school_id=school_id,
        invited_by_id=user_id,
        db=db,
    )
    return {"invitation_token": raw_token}


@router.post("/accept-invite", response_model=UserRead)
async def accept_invite(
    req: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Redeem an invitation token and create the new user's account.

    No authentication is required — this is how a new user gets in.
    The token must not be expired and must not have been used before.
    """
    user = await invite_svc.accept_invitation(req, db)
    return UserRead.model_validate(user)


@router.get("/invite-info/{token}", response_model=InvitationInfo)
async def get_invite_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Preview an invitation without consuming it.

    Called by the frontend before rendering the accept-invite form so the
    invitee can see which school and role they're joining.  No auth required.
    """
    return await invite_svc.get_invitation_info(token, db)


@router.post("/forgot-password", status_code=204)
async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset token.

    Always returns 204 regardless of whether the identifier exists,
    preventing user enumeration.  The raw token is returned in the response
    body during development; in production this will trigger an email/SMS.
    """
    await reset_svc.forgot_password(req, db)


@router.post("/reset-password", status_code=204)
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Consume a reset token and set a new password.

    The token is single-use and expires after 1 hour.
    Returns 400 if the token is invalid, expired, or already used.
    """
    await reset_svc.reset_password(req, db)
