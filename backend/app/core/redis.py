"""
Redis connection management.

Provides a module-level client initialised during the FastAPI lifespan, and a
get_redis() dependency for use in routers and services.

PERMISSION CACHE
----------------
Permission caching helpers (cache_permissions, get_cached_permissions,
invalidate_permissions) live in core/permissions.py — not here.
Keep them there to avoid duplicating serialisation logic.
"""
import redis.asyncio as aioredis
from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import settings

# Module-level client — initialised in app lifespan, None before startup.
redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """Create the Redis connection pool. Called once on app startup."""
    global redis_client
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()


async def close_redis() -> None:
    """Close the Redis connection pool. Called once on app shutdown."""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> aioredis.Redis:
    """FastAPI dependency — returns the live Redis client."""
    if redis_client is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return redis_client


async def get_arq() -> ArqRedis:
    """Create a short-lived ArqRedis pool for job enqueueing. Caller must close it."""
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))
