---
name: verify
description: Project-specific recipe for verifying TTEK-SMS changes against the live docker compose stack. Use this before /verify's generic cold-start when the change touches backend/ or frontend/.
---

# TTEK-SMS verify recipe

No browser automation exists in this sandbox (no Playwright/Chromium/Xvfb,
confirmed 2026-07-11 — recheck before assuming still true). There is also no
GUI verifier here. Given that, verify the **backend at the real HTTP surface**
(live docker compose stack, real Postgres, no mocks) and the **frontend via
SSR page-load + svelte-check** — not full interactive browser drives.

## Stack

```bash
docker compose ps          # api, frontend, db, redis, worker — usually already up
docker compose up -d       # if not
```
- API: `http://localhost:8000` (FastAPI, also serves `/docs`)
- Frontend dev server: `http://localhost:5173` (SvelteKit, Vite HMR)
- DB creds: `ttek` / `changeme` (NOT `postgres` — that role doesn't exist), db `ttek_sms`.
  `docker compose exec db psql -U ttek -d ttek_sms -c "..."` for read-only spot checks.

## Getting a real auth token

Seeded dev accounts exist already (from `backend/scripts/seed_demo_school.py`,
password `Demo1234!` for all of them): `admin@shs.school`, `admin@basic.school`,
`teacher@shs.school`, `finance@shs.school`, `finance@basic.school`, etc.
Two schools exist: "Senior High School" (SHS type) and "Basic School" (BASIC type).

**Never write the token to a file** — Claude Code's auto-mode classifier blocks
credential materialization. Fetch it inline in the same command chain instead:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"login_type":"EMAIL","identifier":"admin@shs.school","password":"Demo1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s "http://localhost:8000/<endpoint>" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

## Backend: drive the real endpoint

Log in, then call the actual changed route with real IDs pulled from the live
DB (`GET /students`, `GET /academic/years`, `GET /academic/classes`, etc.) —
not fixture data from `pytest`. This is real evidence; `pytest` is not (it's
CI's job, and the skill explicitly says don't run it as verification).

After every call: `docker compose logs api --since 2m | grep -iE "error|traceback"`
should be empty. A 500 with a clean traceback in the logs is still a FAIL even
if curl shows a JSON error body.

## Route gotchas (bit me during the 2026-07-11 verification pass)

- Router prefixes aren't always what you'd guess: classes live at
  `/academic/classes`, not `/classes`. Grep `@router.get\|@router.post` in
  `backend/app/routers/*.py` if a route 404s instead of guessing.
- `GET /fees/students/{id}/records` and `/fees/structures` both **require**
  a `term_id` query param — 422 without it.
- Report card format param is case-sensitive uppercase: `?format=SHS`, not
  `shs` — regex-validated, 422 names the pattern if you get it wrong.
- `POST /fees/structures/{id}/bulk-assign` (not `/assign`).
- The demo stack seed data is thin on fees — no fee types/structures/records
  exist by default beyond a bare "Tuition" `FeeType`. Expect to create a
  `FeeStructure` + `bulk-assign` it yourself before you can test payments.

## Destructive paths — don't drive these live

`POST /students/graduation/bulk` (with `deactivate_students: true`) and
`PATCH /students/transfers/{id}/review` (APPROVED) both permanently deactivate
a student and revoke their portal login on this **shared, long-running** dev
stack (docker volumes persist across sessions — it was up 40+ hours during
this check). There's no disposable/reset target. Don't run these against real
seeded students; rely on the pytest integration coverage for that cascade
(real Postgres via test fixtures, not mocked) as corroborating evidence
instead, and say so explicitly in the report.

Non-destructive progression (`POST /students/promotions/bulk`, creating new
classes/years/fee structures) is fine to drive live — it's additive.

## Frontend

No interactive drive possible. Do instead:
- `docker compose exec frontend npm run check` — full svelte-check, compare
  error count against baseline (was 0 as of 2026-07-11; any new errors are a
  regression signal even though this isn't "running the app").
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/<route>` for a
  handful of touched routes — confirms SSR doesn't crash (login page, and any
  public/unauthenticated route). Authenticated routes will 200 with a login
  redirect page, not the real content — this only proves the route doesn't
  500 at the SSR layer, nothing about client-side behavior.
- `docker compose logs frontend --tail 30` after touching files — should show
  clean Vite HMR reloads, no stack traces.

If Playwright/Chromium ever gets added to this repo, prefer driving the
browser directly over this HTTP-surface fallback — update this file's opening
paragraph when that happens.
