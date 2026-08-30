"""
AI provider configuration service.

Same pattern as services/school_config.py for SMS:
  - upsert_ai_config   — create or update credentials for a provider
  - list_ai_configs    — list all configured providers (no api_key)
  - activate_ai_provider — make one provider active, deactivate others
  - delete_ai_config   — remove a provider's credentials
  - get_active_driver  — a school's OWN active driver only, no fallback
                         (used by the "test my key works" endpoint, where
                         silently succeeding against the platform default
                         instead would be misleading)
  - resolve_driver_for_generation — the school's own active driver, falling
                         back to the platform-default row (school_id=NULL)
                         if the school has none — used by every actual
                         generation call site
  - check_daily_limit / increment_usage — Redis counters, per-teacher-per-day
                         always, plus a platform-wide cap when the resolved
                         config is the platform default

Every function here accepts school_id: uuid.UUID | None — passing None
targets the single platform-default row (SQLAlchemy's `== None` already
emits `IS NULL`), used by the superadmin-only platform-default endpoints.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.school import AiConfig, AiProvider
from app.schemas.ai import AiConfigCreate, AiConfigRead
from app.services.ai_driver import AiDriver, build_ai_driver


async def upsert_ai_config(
    school_id: uuid.UUID | None,
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


async def list_ai_configs(school_id: uuid.UUID | None, db: AsyncSession) -> list[AiConfigRead]:
    rows = await db.scalars(
        select(AiConfig)
        .where(AiConfig.school_id == school_id)
        .order_by(AiConfig.provider)
    )
    return [AiConfigRead.model_validate(r) for r in rows]


async def activate_ai_provider(
    school_id: uuid.UUID | None,
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
    school_id: uuid.UUID | None,
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
    """A school's OWN active driver only — never falls back to the platform
    default. Used by the "verify my key works" test endpoint, where silently
    succeeding against Tagnatek's shared config instead of the school's own
    (possibly broken) one would be actively misleading."""
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


async def get_active_driver_for_platform(db: AsyncSession) -> AiDriver:
    """The platform-default row's own active driver — used only by the
    superadmin "verify the platform key works" test endpoint, mirroring
    get_active_driver()'s school-scoped counterpart."""
    cfg = await db.scalar(
        select(AiConfig).where(AiConfig.school_id.is_(None), AiConfig.is_active.is_(True))
    )
    if not cfg:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No platform-default AI provider is configured yet.")
    return build_ai_driver(cfg.provider, cfg.api_key, cfg.model)


async def resolve_driver_for_generation(
    school_id: uuid.UUID, db: AsyncSession,
) -> tuple[AiDriver, AiConfig]:
    """The school's own active config if it has one, else the single
    platform-default row (school_id IS NULL, is_active=True) Tagnatek
    configures once for every school. 503 only if neither exists — meaning
    the platform itself has no default configured yet, not just this school."""
    cfg = await db.scalar(
        select(AiConfig).where(AiConfig.school_id == school_id, AiConfig.is_active.is_(True))
    )
    if not cfg:
        cfg = await db.scalar(
            select(AiConfig).where(AiConfig.school_id.is_(None), AiConfig.is_active.is_(True))
        )
    if not cfg:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No AI provider is configured for this school, and no platform "
            "default is available. Ask your administrator to set one up in "
            "School Setup → AI.",
        )
    return build_ai_driver(cfg.provider, cfg.api_key, cfg.model), cfg


async def check_daily_limit(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    cfg: AiConfig,
    db: AsyncSession,
) -> int:
    """
    Return remaining per-teacher AI generations today for `cfg` (whichever
    config resolve_driver_for_generation() found — the school's own, or the
    platform default). Enforced via Redis key
    ai_usage:{school_id}:{user_id}:{YYYY-MM-DD} — always scoped to the real
    calling school_id even when `cfg` is the shared platform row, so two
    different schools relying on the fallback never share one counter.

    When `cfg` IS the platform default (cfg.school_id is None), an
    additional platform-wide counter is also checked — protects Tagnatek's
    own shared budget from every fallback-relying school combined. A school
    using its own key never touches this second check at all.
    """
    from app.core.redis import redis_client

    if not redis_client:
        return cfg.daily_limit_per_teacher  # Redis unavailable — allow through, don't block teachers

    key = f"ai_usage:{school_id}:{user_id}:{date.today().isoformat()}"
    used_raw = await redis_client.get(key)
    used = int(used_raw) if used_raw else 0
    remaining = cfg.daily_limit_per_teacher - used
    if remaining <= 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily AI generation limit ({cfg.daily_limit_per_teacher}) reached. Resets at midnight.",
        )

    if cfg.school_id is None:
        platform_key = f"ai_usage:platform:{date.today().isoformat()}"
        platform_used_raw = await redis_client.get(platform_key)
        platform_used = int(platform_used_raw) if platform_used_raw else 0
        if platform_used >= settings.platform_ai_daily_limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "The platform's shared AI assistant has reached today's limit. "
                "Ask your administrator to add the school's own AI key in "
                "School Setup → AI for unlimited use.",
            )
    return remaining


async def increment_usage(school_id: uuid.UUID, user_id: uuid.UUID, cfg: AiConfig) -> None:
    """Increment the per-teacher Redis counter (25-hour TTL, clears after
    midnight); also increments the platform-wide counter when `cfg` is the
    platform-default row."""
    from app.core.redis import redis_client
    if not redis_client:
        return
    key = f"ai_usage:{school_id}:{user_id}:{date.today().isoformat()}"
    await redis_client.incr(key)
    await redis_client.expire(key, 90_000)  # 25 hours

    if cfg.school_id is None:
        platform_key = f"ai_usage:platform:{date.today().isoformat()}"
        await redis_client.incr(platform_key)
        await redis_client.expire(platform_key, 90_000)
