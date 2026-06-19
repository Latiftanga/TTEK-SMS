"""
AI provider configuration service.

Same pattern as services/school_config.py for SMS:
  - upsert_ai_config   — create or update credentials for a provider
  - list_ai_configs    — list all configured providers (no api_key)
  - activate_ai_provider — make one provider active, deactivate others
  - delete_ai_config   — remove a provider's credentials
  - get_active_driver  — return a ready AiDriver for the active provider
  - check_daily_limit  — Redis counter; returns remaining generations today
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import AiConfig, AiProvider
from app.schemas.ai import AiConfigCreate, AiConfigRead
from app.services.ai_driver import AiDriver, build_ai_driver


async def upsert_ai_config(
    school_id: uuid.UUID,
    req: AiConfigCreate,
    db: AsyncSession,
) -> AiConfigRead:
    existing = await db.scalar(
        select(AiConfig).where(
            AiConfig.school_id == school_id,
            AiConfig.provider == req.provider,
        )
    )
    if existing:
        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        await db.flush()
        return AiConfigRead.model_validate(existing)

    cfg = AiConfig(school_id=school_id, **req.model_dump())
    db.add(cfg)
    await db.flush()
    return AiConfigRead.model_validate(cfg)


async def list_ai_configs(school_id: uuid.UUID, db: AsyncSession) -> list[AiConfigRead]:
    rows = await db.scalars(
        select(AiConfig)
        .where(AiConfig.school_id == school_id)
        .order_by(AiConfig.provider)
    )
    return [AiConfigRead.model_validate(r) for r in rows]


async def activate_ai_provider(
    school_id: uuid.UUID,
    provider: AiProvider,
    db: AsyncSession,
) -> AiConfigRead:
    cfg = await db.scalar(
        select(AiConfig).where(
            AiConfig.school_id == school_id,
            AiConfig.provider == provider,
        )
    )
    if not cfg:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No {provider.value} config found. Save credentials first.",
        )
    await db.execute(
        update(AiConfig)
        .where(AiConfig.school_id == school_id)
        .values(is_active=False)
    )
    cfg.is_active = True
    await db.flush()
    return AiConfigRead.model_validate(cfg)


async def delete_ai_config(
    school_id: uuid.UUID,
    provider: AiProvider,
    db: AsyncSession,
) -> None:
    cfg = await db.scalar(
        select(AiConfig).where(
            AiConfig.school_id == school_id,
            AiConfig.provider == provider,
        )
    )
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI config not found.")
    await db.delete(cfg)
    await db.flush()


async def get_active_driver(school_id: uuid.UUID, db: AsyncSession) -> AiDriver:
    cfg = await db.scalar(
        select(AiConfig).where(
            AiConfig.school_id == school_id,
            AiConfig.is_active.is_(True),
        )
    )
    if not cfg:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No AI provider is configured for this school. "
            "Ask your administrator to set one up in School Setup → AI.",
        )
    return build_ai_driver(cfg.provider, cfg.api_key, cfg.model)


async def check_daily_limit(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> int:
    """
    Return remaining AI generations for this teacher today.

    Enforced via Redis key ai_usage:{school_id}:{user_id}:{YYYY-MM-DD}.
    Returns remaining count. Raises 429 if the limit is exhausted.
    """
    from app.core.redis import redis_client

    cfg = await db.scalar(
        select(AiConfig).where(
            AiConfig.school_id == school_id,
            AiConfig.is_active.is_(True),
        )
    )
    if not cfg:
        return 0

    limit = cfg.daily_limit_per_teacher
    if not redis_client:
        return limit  # Redis unavailable — allow through, don't block teachers

    key = f"ai_usage:{school_id}:{user_id}:{date.today().isoformat()}"
    used_raw = await redis_client.get(key)
    used = int(used_raw) if used_raw else 0
    remaining = limit - used
    if remaining <= 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily AI generation limit ({limit}) reached. Resets at midnight.",
        )
    return remaining


async def increment_usage(school_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Increment the Redis usage counter; sets 25-hour TTL so it clears after midnight."""
    from app.core.redis import redis_client
    if not redis_client:
        return
    key = f"ai_usage:{school_id}:{user_id}:{date.today().isoformat()}"
    await redis_client.incr(key)
    await redis_client.expire(key, 90_000)  # 25 hours
