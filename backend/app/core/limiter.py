"""
Rate limiting middleware using a Redis sliding window (1-minute fixed window).

Applied as Starlette middleware so it runs before FastAPI's dependency
injection — no decorator interference with type annotations.

PER-PATH LIMITS
---------------
Sensitive unauthenticated endpoints get tighter limits.  Everything else
falls back to settings.rate_limit_per_minute (default 100/min).

CLIENT IP
---------
X-Forwarded-For is trusted for the leftmost address.  In production, ensure
your reverse proxy strips any client-supplied X-Forwarded-For headers before
they reach this app, otherwise clients can spoof their IP.

REDIS UNAVAILABLE
-----------------
If Redis is not yet initialised (e.g. during tests that skip lifespan),
the middleware passes requests through without limiting.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

# Endpoints that need a tighter limit than the global default.
_TIGHT_LIMITS: dict[str, int] = {
    "/auth/login": 10,
    "/auth/superadmin-login": 10,
    "/auth/refresh": 30,
    "/auth/accept-invite": 10,
}


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from app.core.redis import redis_client

        if redis_client is None:
            return await call_next(request)

        path = request.url.path
        limit = _TIGHT_LIMITS.get(path, settings.rate_limit_per_minute)
        ip = _client_ip(request)
        key = f"rl:{ip}:{path}"

        pipe = redis_client.pipeline()
        await pipe.incr(key)
        await pipe.expire(key, 60, nx=True)
        results = await pipe.execute()
        count = results[0]

        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
