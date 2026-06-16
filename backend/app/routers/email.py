"""
Email router — per-school provider configuration and send log.

WORKFLOW FOR SCHOOL ADMINS
--------------------------
1. POST /email/configs           — enter credentials for a provider (SMTP, SendGrid, etc.)
2. GET  /email/configs           — review configured providers (password never returned)
3. POST /email/configs/activate  — choose which provider is currently active
4. DELETE /email/configs/{id}    — remove a provider's credentials
5. GET  /email/logs              — review send history

Only one provider can be active at a time.

Permission map:
  school.manage → configure providers, activate, delete
  school.view   → list configs and view logs
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.school import EmailLog
from app.schemas.school import (
    EmailActivateRequest,
    EmailConfigCreate,
    EmailConfigRead,
    EmailLogRead,
)
from app.services import email_config as email_svc

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/configs", response_model=EmailConfigRead, status_code=201)
async def upsert_email_config(
    req: EmailConfigCreate,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Save or update credentials for an email provider. Password is never returned in GET responses."""
    _, school_id = ids
    return await email_svc.upsert_email_config(school_id, req, db)


@router.get("/configs", response_model=list[EmailConfigRead])
async def list_email_configs(
    ids=Depends(require_permission("school", "view")),
    db: AsyncSession = Depends(get_db),
):
    """List all configured email providers. Passwords are never included."""
    _, school_id = ids
    return await email_svc.list_email_configs(school_id, db)


@router.post("/configs/activate", response_model=EmailConfigRead)
async def activate_email_config(
    req: EmailActivateRequest,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Set one provider as the active email gateway. All others are deactivated."""
    _, school_id = ids
    return await email_svc.activate_email_config(school_id, req.config_id, db)


@router.delete("/configs/{config_id}", status_code=204)
async def delete_email_config(
    config_id: uuid.UUID,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Remove a provider's credentials from this school."""
    _, school_id = ids
    await email_svc.delete_email_config(school_id, config_id, db)


@router.get("/logs", response_model=list[EmailLogRead])
async def list_email_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ids=Depends(require_permission("school", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Return email send history for this school, most recent first."""
    _, school_id = ids
    rows = await db.scalars(
        select(EmailLog)
        .where(EmailLog.school_id == school_id)
        .order_by(EmailLog.sent_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [EmailLogRead.model_validate(r) for r in rows]
