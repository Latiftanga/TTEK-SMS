"""
ARQ background worker.

Startup wires the DB session factory into the job context.  Each job receives
ctx['db'] — an AsyncSessionLocal factory — and opens its own session.

Run (docker compose handles this automatically):
    python -m app.worker

Jobs are registered in WorkerSettings.functions.  Add new jobs here as phases
are built — never import the worker module from the API to avoid coupling.

Planned jobs by phase:
  Phase 3:  generate_school_calendar
  Phase 7:  bulk_generate_report_cards
  Phase 9:  recompute_fee_summary
  Phase 11: waec_export
"""
from arq import run_worker
from arq.connections import RedisSettings
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine

# Every mapped model must be imported before any job runs — SQLAlchemy
# resolves relationship() string references (e.g. StaffMember -> "StaffPosition")
# lazily, against whatever classes have been imported into the process by
# the time the first query fires. The worker is a separate process from the
# API server (`python -m app.worker`, not uvicorn), so it can't rely on
# main.py's own imports — it needs this exact same explicit sweep
# tests/conftest.py already does for the same reason.
from app.models import (  # noqa: F401
    academic, assessments, attendance, auth, documents, fees,
    housing, school, staff, staff_history, students,
)
from app.services.bulk_report_job import bulk_generate_report_cards


# ── Lifecycle hooks ───────────────────────────────────────────────────────────

async def startup(ctx: dict) -> None:
    """Probe the DB and store the session factory in the job context."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    ctx["db"] = AsyncSessionLocal
    print("[worker] startup complete — DB reachable")


async def shutdown(ctx: dict) -> None:
    """Dispose the DB connection pool on clean exit."""
    await engine.dispose()
    print("[worker] shutdown complete")


# ── Jobs ──────────────────────────────────────────────────────────────────────

async def test_job(ctx: dict, message: str) -> str:
    """Smoke-test job — verifies the worker can process a job and reach the DB."""
    async with ctx["db"]() as session:
        await session.execute(text("SELECT 1"))
    print(f"[worker] test_job: {message}")
    return f"done: {message}"


# ── Worker settings ───────────────────────────────────────────────────────────

class WorkerSettings:
    functions = [test_job, bulk_generate_report_cards]

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    on_startup = startup
    on_shutdown = shutdown

    job_timeout = 300
    max_tries = 3
    health_check_interval = 60


if __name__ == "__main__":
    run_worker(WorkerSettings)
