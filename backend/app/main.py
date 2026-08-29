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
from app.routers import academic, academic_structure, ai, assessment_types, assessments, attendance, auth, dashboard, documents, email, fees, grading, holidays, housing, lesson_plans, permissions, portal, programme_summary, report_cards, school_periods, schools, scoring, sms, staff, staff_admin, staff_category, staff_photo, staff_records, students, students_detail, students_enrollment, students_lifecycle, students_transcript, subject_summary, sync, timetable

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
    # *.localhost is always loopback in every modern browser (RFC 6761) — a
    # real client on the public internet can never present this Origin, so
    # it's safe to allow unconditionally. This is what lets subdomain-based
    # multi-tenancy (branded school login pages) be tested locally via
    # e.g. http://amass.localhost:5173 with no /etc/hosts edit, no DNS, and
    # no wildcard TLS setup — see CLAUDE.md's local-testing note.
    allow_origin_regex=r"^http://[a-z0-9-]+\.localhost(:\d+)?$",
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
app.include_router(school_periods.router)
app.include_router(academic.router)
app.include_router(academic_structure.router)
app.include_router(timetable.router)
app.include_router(subject_summary.router)
app.include_router(programme_summary.router)
app.include_router(grading.router)
app.include_router(assessment_types.router)  # /types, /type-presets — literal segments, must precede assessments.router's /{assessment_id}
app.include_router(assessments.router)
app.include_router(scoring.router)
app.include_router(staff_category.router)
app.include_router(staff.router)
app.include_router(staff_records.router)
app.include_router(staff_admin.router)
app.include_router(staff_photo.router)
app.include_router(students.router)
app.include_router(students_enrollment.router)
app.include_router(students_lifecycle.router)
app.include_router(students_transcript.router)
app.include_router(students_detail.router)  # /{student_id} — must be last of the students_* routers
app.include_router(housing.router)
app.include_router(fees.router)
app.include_router(report_cards.router)
app.include_router(documents.router)
app.include_router(lesson_plans.router)
app.include_router(portal.router)
app.include_router(sync.router)
app.include_router(sms.router)
app.include_router(email.router)
app.include_router(permissions.router)
app.include_router(ai.router)
app.include_router(dashboard.router)
app.include_router(holidays.router)

# ── Static file serving (local storage only) ──────────────────────────────────
# In production with R2, logo_path becomes a full CDN URL and this mount
# is not used.  It is safe to keep it registered — it simply won't be hit.
if settings.storage_backend == "LOCAL":
    uploads_dir = Path(settings.local_upload_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
