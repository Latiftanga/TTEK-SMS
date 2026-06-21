# TTEK-SMS

Ghana GES-aligned School Management System by Tagnatek.
Multi-school SaaS — FastAPI + SvelteKit + PostgreSQL + Redis.

## Quick start (new machine)

**Prerequisites:** Docker Desktop (or Docker Engine + Compose plugin)

```bash
git clone https://github.com/Latiftanga/TTEK-SMS.git
cd TTEK-SMS
make setup
```

That single command:
1. Copies `.env.example` → `.env`
2. Builds and starts all Docker services
3. Runs database migrations automatically
4. Seeds reference data (Ghana regions, districts, GES holidays)
5. Creates the first superadmin account

When it finishes:
| Service | URL |
|---|---|
| API (Swagger docs) | http://localhost:8000/docs |
| Frontend | http://localhost:5173 |

Default superadmin credentials are in `.env` (`SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD`). Change them before deploying.

## Day-to-day commands

```bash
make dev          # start services
make down         # stop services
make logs         # follow API logs
make shell        # bash inside API container
make test         # run pytest
make migrate      # run pending migrations
make reset        # wipe all data and start fresh (dev only)
```

Run `make` with no arguments to see the full command list.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (async) · SQLAlchemy 2 · Alembic · PostgreSQL 16 |
| Cache / Queue | Redis · ARQ |
| Frontend | SvelteKit 2 · Tailwind v4 · TanStack Query |
| PDF | WeasyPrint (generated on demand, never stored) |
| SMS | AfricasTalking · Hubtel · Arkesel · WiGal · Twilio |
| Storage | Local `/uploads` → Cloudflare R2 (zero schema change) |

## Environment variables

Edit `.env` after `make setup`. Key variables:

| Variable | Purpose |
|---|---|
| `APP_SECRET_KEY` | JWT signing key — use a long random string in production |
| `HMAC_SECRET_KEY` | QR code verification — separate long random string |
| `POSTGRES_PASSWORD` | Database password |
| `SUPERADMIN_EMAIL/PASSWORD` | First admin account |
| `PLATFORM_DOMAIN` | Your deployment domain (e.g. `ttek-sms.com`) |

Leave SMS, R2, and Sentry fields blank during local development.

## Architecture notes

- Every table has `school_id` — row-level isolation enforced at the service layer
- Fee balances are never stored — computed live or from `StudentFeeSummary` cache
- Class teacher assigned per academic year (not per term)
- Report cards generated on demand by WeasyPrint — never written to disk
- Offline score sync via Dexie WriteOutbox with conflict detection
