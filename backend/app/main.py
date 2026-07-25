"""
FastAPI application entry point.

Wires together: lifespan (Redis), middleware (CORS, rate-limiting),
global exception handling, Sentry, and all routers.

CORS origins are loaded from settings.cors_origins so they can be changed
via environment variable without a code change.
"""
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.limiter import RateLimitMiddleware
from app.core.redis import close_redis, init_redis
from app.routers import academic, academic_structure, ai, assessments, attendance, auth, dashboard, documents, email, fees, housing, permissions, portal, report_cards, schools, sms, staff, staff_admin, staff_category, staff_records, students, students_detail, students_enrollment, students_lifecycle, sync

# ── Sentry ───────────────────────────────────────────────────────────────────
if settings.sentry_dsn and settings.sentry_dsn.startswith("https://"):
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.2 if settings.is_production else 1.0,
        send_default_pii=False,
    )


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_redis()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TTEK-SMS API",
    description="Tagnatek School Management System — Ghana GES-aligned",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "env": settings.app_env}


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Let process-level signals propagate — do not swallow them as HTTP 500s.
    if isinstance(exc, (SystemExit, KeyboardInterrupt)):
        raise
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)
    if settings.is_development:
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(schools.router)
app.include_router(attendance.router)
app.include_router(academic.router)
app.include_router(academic_structure.router)
app.include_router(assessments.router)
app.include_router(staff_category.router)
app.include_router(staff.router)
app.include_router(staff_records.router)
app.include_router(staff_admin.router)
app.include_router(students.router)
app.include_router(students_enrollment.router)
app.include_router(students_lifecycle.router)
app.include_router(students_detail.router)  # /{student_id} — must be last of the students_* routers
app.include_router(housing.router)
app.include_router(fees.router)
app.include_router(report_cards.router)
app.include_router(documents.router)
app.include_router(portal.router)
app.include_router(sync.router)
app.include_router(sms.router)
app.include_router(email.router)
app.include_router(permissions.router)
app.include_router(ai.router)
app.include_router(dashboard.router)

# ── Static file serving (local storage only) ──────────────────────────────────
# In production with R2, logo_path becomes a full CDN URL and this mount
# is not used.  It is safe to keep it registered — it simply won't be hit.
if settings.storage_backend == "LOCAL":
    uploads_dir = Path(settings.local_upload_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
