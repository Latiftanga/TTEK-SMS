# Deploying TTEK-SMS

This covers a single-VPS deployment via `docker-compose.prod.yml` — one
server, one Docker Compose stack, everything on it. This is prep for when
you're actually ready to deploy; nothing here has been run against a real
server.

Not covered here (deliberately out of scope for this pass — see the note at
the bottom of each): TLS/domain setup, structured logging, database backup
automation, Cloudflare R2 object storage, SMS/email credential encryption
at rest, and any CI/CD auto-deploy pipeline. CI (`.github/workflows/ci.yml`)
only runs tests today — there is no automated build/push/deploy anywhere.

## 1. Provision a server

Any VPS with Docker + the Compose plugin installed (Ubuntu 22.04/24.04 is a
safe default). You need enough RAM for Postgres + Redis + 4 uvicorn workers
+ the ARQ worker + the frontend server + Caddy — 2 vCPU / 4 GB is a
reasonable starting point for a school-SaaS workload at modest scale; resize
later if needed.

## 2. Clone the repo and create a real `.env`

```bash
git clone https://github.com/Latiftanga/TTEK-SMS.git
cd TTEK-SMS
cp .env.example .env
```

Then edit `.env` — every value below **must** change from `.env.example`'s
dev placeholder before this will boot in production:

| Variable | Set to |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_SECRET_KEY` | a real random secret — `openssl rand -hex 32` |
| `HMAC_SECRET_KEY` | a second, different real random secret — `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | a real database password |
| `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` | real first-admin credentials |
| `PLATFORM_DOMAIN` / `PUBLIC_PLATFORM_DOMAIN` | your real owned domain, once you have one (leave both unset until then — see the comment already in `.env.example` explaining why) |

`APP_SECRET_KEY`/`HMAC_SECRET_KEY`/`POSTGRES_PASSWORD`/`SUPERADMIN_PASSWORD`
are enforced: the app refuses to start at all (`ValueError` at boot, before
uvicorn even binds a port) if `APP_ENV=production` and any of these are
still at their insecure `.env.example` default
(`backend/app/core/config.py::validate_production_secrets`).

## 3. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds the backend, worker, frontend, and proxy images and starts
everything. `alembic upgrade head` and `scripts/seed_reference_data.py` run
automatically on every `api` container start — both are idempotent, so this
is safe on every redeploy, not just the first one.

Check everything came up healthy:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
curl http://localhost/health
```

## 4. Create the first superadmin (one-time)

Unlike the dev stack, `docker-compose.prod.yml` does **not** auto-run
`create_superadmin.py` on boot — creating the platform's first admin account
is a deliberate one-time action, not something to silently repeat on every
container restart. Run it once, after the stack is up:

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/create_superadmin.py
```

Log in at `http://<your-server>/` with `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD`
from `.env`, and onboard your first real school from there (superadmin
dashboard → "Onboard school").

## 5. What's actually reachable

Only the `proxy` service (Caddy, port 80) is published to the host — `db`,
`redis`, `api`, `worker`, and `frontend` are only reachable on the internal
Compose network. Caddy (`Caddyfile` at the repo root) routes `/api/*` to the
backend and everything else to the frontend — this is required, not
cosmetic: the frontend's axios client calls a relative `/api` path, which in
development is proxied by Vite's own dev server (`vite.config.ts`) — that
mechanism doesn't exist once the frontend is a real built `adapter-node` app,
so without Caddy (or something equivalent) in front, every API call from the
browser would 404 in production.

## 6. Known gaps to revisit before you actually rely on this in production

These are real, not hidden — flagged here rather than silently left for you
to discover:

- **TLS/domain.** `Caddyfile` serves plain HTTP on `:80` — no certificate,
  no real domain wired up. Once you own a domain and point its DNS (or
  Cloudflare) at this server, replace `:80` in `Caddyfile` with the real
  domain and restart the `proxy` service — Caddy auto-provisions Let's
  Encrypt HTTPS from that one change, no other code involved. This mirrors
  the "Phase B" TLS/DNS step already scoped as ops-only in earlier planning
  (see CLAUDE.md's 12ba entry) — genuinely a config change at deploy time,
  not something to pre-build speculatively here.
- **`ORIGIN` / CSRF on real subdomains.** This app serves every school on
  its own subdomain, which is a different shape from adapter-node's
  single-`ORIGIN` assumption (used for its built-in CSRF Origin check and
  absolute-URL building). Test real form submissions (login, etc.) against
  your actual domain once DNS is live — `docker-compose.prod.yml`'s comment
  on the `frontend` service's `ORIGIN` var flags exactly what to check if
  something breaks there.
- **File storage stays local-disk** (named Docker volumes
  `uploads_data`/`secure_uploads_data`), fine for one VPS/one instance —
  would need a real Cloudflare R2 implementation (currently just scaffolded
  settings fields, `backend/app/services/storage.py` has no R2 code path)
  before this could ever scale to multiple backend replicas.
- **No database backup automation.** Set up `pg_dump` on a cron, or migrate
  to a managed Postgres provider with automatic backups, before real school
  data lives on this — nothing here does that for you.
- **SMS/email provider credentials are stored in the database as plaintext**
  (per-school `SmsConfig`/`EmailConfig` rows, set via each school's own
  Setup page) — already flagged in the driver files themselves as a
  pre-production TODO (encrypt at the column level, or move to a secrets
  manager).
- **No structured logging.** The app currently relies on uvicorn/ARQ's
  default stdout output plus Sentry (already wired — set `SENTRY_DSN` in
  `.env` to enable error tracking) for visibility. Fine at small scale;
  revisit if debugging in production gets painful.
