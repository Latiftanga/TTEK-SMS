"""Email provider configuration — list, upsert, activate, delete."""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import EmailConfig
from app.schemas.school import EmailConfigCreate, EmailConfigRead


async def list_email_configs(school_id: uuid.UUID, db: AsyncSession) -> list[EmailConfigRead]:
    rows = await db.scalars(
        select(EmailConfig)
        .where(EmailConfig.school_id == school_id)
        .order_by(EmailConfig.created_at)
    )
    return [EmailConfigRead.model_validate(r) for r in rows]


async def upsert_email_config(
    school_id: uuid.UUID,
    req: EmailConfigCreate,
    db: AsyncSession,
) -> EmailConfigRead:
    """Create or replace credentials for a provider. One row per provider per school."""
    existing = await db.scalar(
        select(EmailConfig).where(
            EmailConfig.school_id == school_id,
            EmailConfig.provider == req.provider,
        )
    )
    if existing:
        existing.host = req.host
        existing.port = req.port
        existing.username = req.username
        if req.password is not None:
            existing.password = req.password
        existing.from_name = req.from_name
        existing.from_address = str(req.from_address)
        existing.use_tls = req.use_tls
        cfg = existing
    else:
        cfg = EmailConfig(
            school_id=school_id,
            provider=req.provider,
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
            from_name=req.from_name,
            from_address=str(req.from_address),
            use_tls=req.use_tls,
            is_active=False,
        )
        db.add(cfg)

    await db.flush()
    return EmailConfigRead.model_validate(cfg)


async def activate_email_config(
    school_id: uuid.UUID,
    config_id: uuid.UUID,
    db: AsyncSession,
) -> EmailConfigRead:
    """Set one config as active; deactivate all others for this school."""
    target = await db.scalar(
        select(EmailConfig).where(
            EmailConfig.id == config_id,
            EmailConfig.school_id == school_id,
        )
    )
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email config not found.")

    all_configs = await db.scalars(
        select(EmailConfig).where(EmailConfig.school_id == school_id)
    )
    for cfg in all_configs:
        cfg.is_active = cfg.id == config_id

    await db.flush()
    return EmailConfigRead.model_validate(target)


async def delete_email_config(
    school_id: uuid.UUID,
    config_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    cfg = await db.scalar(
        select(EmailConfig).where(
            EmailConfig.id == config_id,
            EmailConfig.school_id == school_id,
        )
    )
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email config not found.")
    await db.delete(cfg)
    await db.flush()
