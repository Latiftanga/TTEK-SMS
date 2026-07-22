"""Grant and revoke guardian portal access.

Portal login uses PHONE — the guardian's own phone number is the username.
Unlike a student's admission number (public, predictable, safe to use as an
initial password), a guardian has no equivalent safe secret, so the initial
password is random and unusable. grant_portal_access SMS's the guardian
telling them to use "Forgot password?" with their own phone number, which
reuses the existing OTP reset flow (services/auth_reset.py) unchanged — no
new onboarding-password mechanism needed.
"""
from __future__ import annotations
import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.auth import LoginType, User
from app.models.school import School
from app.models.students import Guardian
from app.schemas.students import GuardianPortalAccessResult


async def grant_portal_access(
    guardian_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> GuardianPortalAccessResult:
    guardian = await db.get(Guardian, guardian_id)
    if not guardian or guardian.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found.")

    existing = await db.scalar(select(User).where(User.guardian_id == guardian_id))
    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guardian already has portal access.",
            )
        existing.is_active = True
        existing.phone = guardian.phone
        existing.password_hash = hash_password(secrets.token_urlsafe(24))
    else:
        db.add(User(
            school_id=school_id,
            login_type=LoginType.PHONE,
            phone=guardian.phone,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            guardian_id=guardian_id,
            is_active=True,
        ))

    try:
        await db.flush()
    except IntegrityError:
        # User.phone is unique platform-wide (see models/auth.py's User docstring) —
        # this guardian's phone is already claimed by another account.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already registered to another account on this platform.",
        )

    sms_sent = await _notify_guardian(guardian, school_id, db)
    return GuardianPortalAccessResult(has_portal_access=True, phone=guardian.phone, sms_sent=sms_sent)


async def revoke_portal_access(
    guardian_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    guardian = await db.get(Guardian, guardian_id)
    if not guardian or guardian.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found.")

    user = await db.scalar(
        select(User).where(User.guardian_id == guardian_id, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guardian does not have active portal access.",
        )
    user.is_active = False
    await db.flush()


async def _notify_guardian(guardian: Guardian, school_id: uuid.UUID, db: AsyncSession) -> bool:
    school = await db.get(School, school_id)
    school_name = school.name if school else "the school"
    msg = (
        f"Dear {guardian.first_name}, you now have access to the {school_name} parent portal. "
        f"Tap 'Forgot password?' and enter your phone number to set a password, "
        f"then log in with your phone number."
    )
    from app.services.sms_notifications import notify_portal_access
    return await notify_portal_access(guardian.phone, msg, school_id, "GUARDIAN_PORTAL", guardian.id, db)
