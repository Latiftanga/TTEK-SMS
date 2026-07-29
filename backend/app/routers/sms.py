"""
SMS router — per-school provider configuration and message dispatch.

WORKFLOW FOR SCHOOL ADMINS
--------------------------
1. POST /sms/configs         — enter credentials for a provider (e.g. AfricasTalking)
2. GET  /sms/configs         — review configured providers (credentials never returned)
3. POST /sms/configs/activate — choose which provider is currently active
4. POST /sms/send            — send a custom message to one or more guardian phones
5. GET  /sms/logs            — review sent message history

Only one provider can be active at a time.  Activating a new provider
automatically deactivates the previous one.

Permission map:
  school.manage → configure providers, activate, delete, send
  school.view   → list configs and view logs (read-only)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.school import SmsLog, SmsProvider
from app.schemas.school import SmsConfigCreate, SmsConfigRead
from app.schemas.sms import (
    SmsActivateRequest, SmsLogRead,
    SmsSendRequest, SmsSendResponse, SmsSendResult,
)
from app.services import school_config as config_svc
from app.services import sms_notifications as sms_svc

router = APIRouter(prefix="/sms", tags=["sms"])


# ── Provider configuration ────────────────────────────────────────────────────

@router.post("/configs", response_model=SmsConfigRead, status_code=201)
async def upsert_sms_config(
    req: SmsConfigCreate,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Save or update credentials for an SMS provider.

    Call this once per provider.  Credentials (api_key, api_secret) are
    stored server-side; they are NEVER returned in any GET response.
    After saving, call POST /sms/configs/activate to make it active.
    """
    _, school_id = ids
    return await config_svc.upsert_sms_config(school_id, req, db)


@router.get("/configs", response_model=list[SmsConfigRead])
async def list_sms_configs(
    ids=Depends(require_permission("school", "view")),
    db: AsyncSession = Depends(get_db),
):
    """
    List all configured SMS providers for this school.

    Shows provider name, sender ID, and whether it is currently active.
    API keys and secrets are never included in this response.
    """
    _, school_id = ids
    return await config_svc.list_sms_configs(school_id, db)


@router.post("/configs/activate", response_model=SmsConfigRead)
async def activate_sms_provider(
    req: SmsActivateRequest,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Set one provider as the active SMS gateway for this school.

    All other configured providers are deactivated automatically.
    The provider must already have credentials saved via POST /sms/configs.
    """
    _, school_id = ids
    return await config_svc.activate_sms_provider(school_id, req.provider, db)


@router.delete("/configs/{provider}", status_code=204)
async def delete_sms_config(
    provider: SmsProvider,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Remove a provider's credentials from this school."""
    _, school_id = ids
    await config_svc.delete_sms_config(school_id, provider, db)


# ── Manual send ───────────────────────────────────────────────────────────────

@router.post("/send", response_model=SmsSendResponse)
async def send_manual(
    req: SmsSendRequest,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a custom SMS message to one or more phone numbers.

    Requires an active provider to be configured.  Returns a per-number
    success/failure breakdown.  All attempts are logged to /sms/logs.
    """
    _, school_id = ids
    try:
        results = await sms_svc.send_manual(req.phones, req.message, school_id, db)
    except ValueError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    # Pair results with phones (same order)
    paired = [
        SmsSendResult(phone=phone, success=r.success, error=r.error)
        for phone, r in zip(req.phones, results)
    ]
    return SmsSendResponse(
        sent=sum(1 for r in results if r.success),
        failed=sum(1 for r in results if not r.success),
        results=paired,
    )


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=list[SmsLogRead])
async def list_sms_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ids=Depends(require_permission("school", "view")),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the SMS send history for this school, most recent first.

    Includes both automatically triggered messages (fee receipts, attendance
    alerts, report cards) and manually sent messages.
    """
    _, school_id = ids
    rows = await db.scalars(
        select(SmsLog)
        .where(SmsLog.school_id == school_id)
        .order_by(SmsLog.sent_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [SmsLogRead.model_validate(r) for r in rows]
