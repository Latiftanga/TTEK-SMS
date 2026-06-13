"""
Invitation service — create, preview, and accept staff invitations.

Separated from services/auth.py to keep file sizes under 300 lines.

INVITATION FLOW
---------------
1. Admin calls POST /auth/invite → create_invitation() returns a raw token.
   The raw token should be included in an email/SMS link sent to the invitee.
   Only the SHA-256 hash is stored in the database.

2. Invitee opens the link → frontend calls GET /auth/invite-info/{token}
   → get_invitation_info() returns school name, position, and email/phone.
   The frontend shows "You've been invited as [role] to [school]" before
   the invitee sets their password.

3. Invitee submits the form → POST /auth/accept-invite
   → accept_invitation() creates the User account and marks the token used.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_invitation_token,
    hash_password,
    hash_token,
    invitation_expiry,
)
from app.models.auth import LoginType, StaffPosition, User, UserInvitation
from app.models.school import School
from app.schemas.auth import AcceptInvitationRequest, InvitationCreate, InvitationInfo


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_invitation(
    req: InvitationCreate,
    school_id: uuid.UUID,
    invited_by_id: uuid.UUID,
    db: AsyncSession,
) -> str:
    """
    Generate an invitation for a new staff member and return the raw token.

    The raw token is meant to be included in an email or SMS link.
    Only the SHA-256 hash is stored in the database — the raw token
    is never persisted.

    Returns:
        The raw invitation token string.

    Raises:
        400  Neither email nor phone was provided.
    """
    if not req.email and not req.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of 'email' or 'phone' is required for the invitation.",
        )

    raw_token, token_hash = create_invitation_token()

    invitation = UserInvitation(
        school_id=school_id,
        email=req.email.lower().strip() if req.email else None,
        phone=req.phone.strip() if req.phone else None,
        position_id=req.position_id,
        staff_member_id=req.staff_member_id,
        token_hash=token_hash,
        expires_at=invitation_expiry(),
        invited_by_id=invited_by_id,
    )
    db.add(invitation)
    await db.flush()

    return raw_token


async def get_invitation_info(token: str, db: AsyncSession) -> InvitationInfo:
    """
    Return a read-only preview of an invitation without consuming it.

    Called by the frontend before showing the accept-invite form so the
    invitee knows which school and role they're joining.

    Raises:
        404  Token not found.
    """
    token_hash = hash_token(token)
    invitation = await db.scalar(
        select(UserInvitation).where(UserInvitation.token_hash == token_hash)
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found.",
        )

    school = await db.get(School, invitation.school_id)
    position = await db.get(StaffPosition, invitation.position_id) if invitation.position_id else None

    return InvitationInfo(
        school_name=school.name if school else "Unknown school",
        position_name=position.name if position else None,
        email=invitation.email,
        phone=invitation.phone,
        is_expired=invitation.expires_at < _utcnow(),
        is_accepted=invitation.accepted_at is not None,
    )


async def accept_invitation(req: AcceptInvitationRequest, db: AsyncSession) -> User:
    """
    Redeem an invitation token and create the user's account.

    The login_type is inferred from the invitation:
      - If invitation.email is set      → login_type = EMAIL
      - If only invitation.phone is set → login_type = PHONE

    Side effects:
      - Creates a new User row.
      - Stamps invitation.accepted_at (marks the token as used).

    Raises:
        404  Token not found or already accepted.
        400  Token has expired (72 hours after creation by default).
    """
    token_hash = hash_token(req.token)

    invitation = await db.scalar(
        select(UserInvitation).where(
            UserInvitation.token_hash == token_hash,
            UserInvitation.accepted_at.is_(None),
        )
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has already been accepted.",
        )

    if invitation.expires_at < _utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired. Ask an admin to send a new one.",
        )

    login_type = LoginType.EMAIL if invitation.email else LoginType.PHONE
    user = User(
        school_id=invitation.school_id,
        login_type=login_type,
        email=invitation.email,
        phone=invitation.phone,
        password_hash=hash_password(req.password),
        staff_member_id=invitation.staff_member_id,   # links to professional profile
        is_active=True,
    )
    db.add(user)
    invitation.accepted_at = _utcnow()
    await db.flush()

    return user
