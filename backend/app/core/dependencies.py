"""
FastAPI dependency functions — the security layer for all endpoints.

This module is the single place where Bearer tokens are decoded, the caller's
identity is established, and access rules are enforced before any endpoint
handler runs.

HOW TO SECURE AN ENDPOINT
--------------------------
Any authenticated user (just needs a valid token):

    @router.get("/profile")
    async def get_profile(ids = Depends(require_auth), db = Depends(get_db)):
        user_id, school_id = ids

Permission-gated (staff must have the permission in their role or personal overrides):

    @router.post("/fees/pay")
    async def collect_fee(ids = Depends(require_permission("fees", "collect")), ...):
        user_id, school_id = ids

Superadmin-only operations (platform management — registering schools, etc.):

    @router.post("/schools")
    async def register_school(ids = Depends(require_superadmin), ...):
        user_id, _ = ids

WHAT "ids" CONTAINS
--------------------
Every dependency returns a two-tuple:  (user_id: UUID, school_id: UUID | None)
  - user_id    — the authenticated user's primary key in the `user` table
  - school_id  — the school the user belongs to; None for superadmin users
                 who are not tied to any single school

TOKEN LIFECYCLE (for debugging auth failures)
---------------------------------------------
1. POST /auth/login  →  { access_token (15 min), refresh_token (7 days) }
2. Client sends:  Authorization: Bearer <access_token>
3. These dependencies decode the token and extract user_id / school_id.
4. POST /auth/refresh  →  new { access_token, refresh_token }.
   The old refresh_token is IMMEDIATELY revoked (token rotation).
   Reusing a revoked refresh_token → 401.
5. POST /auth/logout revokes the refresh_token. Access tokens are stateless
   and cannot be individually revoked before they expire.

COMMON ERROR CODES
------------------
  403  No Authorization header present (HTTPBearer raises this)
  401  Token is invalid, expired, or for the wrong token type
  401  User account has been deactivated
  403  User lacks the required permission
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.database import get_db
from app.core.permissions import resolve_permissions

# FastAPI uses this to extract the "Bearer <token>" header.
# auto_error=True (default) means it raises 403 if the header is missing.
_bearer = HTTPBearer()

# Type alias used throughout this module for clarity.
UserIdentity = tuple[uuid.UUID, uuid.UUID | None]


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserIdentity:
    """
    Validate the Bearer token and return (user_id, school_id).

    Raises:
        403  if the Authorization: Bearer header is missing entirely
        401  if the token is expired, malformed, or has the wrong type
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload.user_id, payload.school_id


# Keep the old name as an alias so existing callers don't break during migration.
# New code should use require_auth.
get_current_user_id = require_auth


async def require_superadmin(
    ids: UserIdentity = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> UserIdentity:
    """
    Ensure the caller is the platform superadmin.

    Superadmin has no school_id and is the only account that can register
    new schools, manage platform-wide settings, and create other superadmins.

    Raises:
        401  invalid / expired token
        403  user is not a superadmin
    """
    from app.models.auth import User

    user_id, school_id = ids
    user = await db.get(User, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or has been deactivated.",
        )

    if not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires superadmin privileges.",
        )

    return ids


def require_permission(module: str, action: str):
    """
    Return a FastAPI dependency that enforces a specific permission.

    Uses the 3-layer permission system (see core/permissions.py).
    Superadmin bypasses all permission checks.

    Args:
        module: The feature area, e.g. "students", "fees", "attendance".
        action: The specific operation, e.g. "view", "create", "approve_scores".

    Usage:
        @router.post("/fees/pay")
        async def pay(ids = Depends(require_permission("fees", "collect"))):
            ...

    Raises:
        401  invalid / expired token or deactivated account
        403  user does not have the required permission
    """
    async def _enforce(
        ids: UserIdentity = Depends(require_auth),
        db: AsyncSession = Depends(get_db),
    ) -> UserIdentity:
        from app.models.auth import User

        user_id, _ = ids
        user = await db.get(User, user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or has been deactivated.",
            )

        # Superadmin is never subject to permission checks.
        if user.is_superadmin:
            return ids

        # Only staff members carry permissions.  Students and anonymous users
        # (e.g. users created via invitation but not yet linked to a staff record)
        # cannot perform permission-gated actions.
        if not user.staff_member_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission denied: '{module}.{action}' requires a staff account. "
                    "This user is not linked to a staff member record."
                ),
            )

        perms = await resolve_permissions(user.staff_member_id, db)
        if not perms.get(f"{module}.{action}", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: your role does not allow '{module}.{action}'.",
            )

        return ids

    return _enforce
