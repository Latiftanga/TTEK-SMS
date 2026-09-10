# TTEK-SMS — CLAUDE.md
# Read this file at the start of every session before writing any code.

## What this project is
Ghana GES-aligned School Management System for Tagnatek.
Multi-school SaaS platform. Every school feels like the system was built for them alone.

## Tech stack
- Backend:   FastAPI (async) + SQLAlchemy 2 + Alembic + PostgreSQL 16 + Redis + ARQ
- Frontend:  SvelteKit 2 + Tailwind v4 + Dexie.js + TanStack Query + Zustand
- PDF:       WeasyPrint (generated on demand, never stored)
- SMS:       SmsService driver abstraction (AfricasTalking, Hubtel, Arkesel, WiGal, Twilio)
- Storage:   Local /uploads now → Cloudflare R2 later (zero schema change)
- Mobile:    PWA now → Capacitor (Phase 7+) → React Native only if needed

## Absolute rules — never break these
- Every table has school_id (UUID FK → School) — RLS enforced at DB layer
- Grade is NEVER stored on Score — resolved at query time from GradingScale
- Fee balance is NEVER stored — computed live or read from StudentFeeSummary cache
- Class name is NEVER stored — computed: level + year_group + programme + stream
- AttendanceRecord always uses school_calendar_id FK — never a raw date field
- Offline score sync always sends offline_session_started_at — server checks for conflicts
- StaffPermission personal override always beats PositionPermission template
- Report cards generated on demand by WeasyPrint — never written to disk

## File size rule
No file exceeds 300 lines. If a file approaches 300 lines, split it before continuing.

## Folder structure
```
ttek-sms/
├── CLAUDE.md                          ← this file — read first every session
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── blueprint/
│   └── ttek_sms_blueprint_v4.html     ← full architecture reference
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py              ← Pydantic Settings
│       │   ├── database.py            ← async engine + session
│       │   ├── redis.py               ← async Redis connection
│       │   ├── auth.py                ← JWT + session logic
│       │   └── permissions.py        ← 3-layer resolution + cache
│       ├── models/
│       │   ├── base.py                ← Base, TimestampMixin, school_id mixin
│       │   ├── school.py              ← Group 1: GhanaRegion, GhanaDistrict, School, SchoolConfig, SmsConfig
│       │   ├── auth.py                ← Group 2: User, UserSession, UserInvitation, StaffPosition, PositionPermission, StaffPermission, AuditLog
│       │   ├── staff.py               ← Group 3: StaffMember, StaffEmergencyContact, StaffPromotion, StaffQualification, StaffLeave
│       │   ├── academic.py            ← Group 4: AcademicYear, AcademicTerm, SHSProgramme, SubjectCatalogue, Subject, Class, ClassSubject, ClassTeacher, SubjectTeacher
│       │   ├── students.py            ← Group 5: Student, StudentMedicalRecord, Guardian, StudentGuardian, StudentEnrollment, TermEnrollment, SubjectRegistration, TransferRequest
│       │   ├── housing.py             ← Group 6: House, HouseMaster, Room, StudentHouseAssignment, NightRollCall, Exeat
│       │   ├── attendance.py          ← Group 7: SchoolSchedule, GhanaPublicHoliday, SchoolCalendar, SchoolPeriod, AttendanceRecord
│       │   ├── assessments.py         ← Group 8: GradingScale, Grade, AssessmentType, Assessment, Score, ScoreAuditLog, StudentBehaviourRecord
│       │   ├── fees.py                ← Group 9: FeeType, FeeStructure, StudentFeeRecord, FeePayment, FeeDiscount, FeeInstalmentPlan, StudentFeeSummary
│       │   └── documents.py           ← Group 10: DocumentRecord, ImportBatch, ImportRow, GraduationRecord, OfflineSyncConflict
│       ├── routers/                   ← one file per feature area
│       ├── services/                  ← business logic, one file per domain
│       ├── schemas/                   ← Pydantic schemas, one file per group
│       └── tests/                     ← mirrors routers/ structure
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── app.html
        ├── routes/
        └── lib/
            ├── api/                   ← API call functions
            ├── stores/                ← Zustand stores
            ├── components/            ← shared components
            └── offline/
                └── outbox.ts          ← Dexie WriteOutbox
```

## Current phase
Phase: 12 — Frontend Build
Status: IN PROGRESS
Started: 2026-06-13

Detailed session-by-session history (bug fixes found, design decisions, verification steps, phase completion checklists) has moved to the `session-history` skill — invoke it when you need historical context (why something works a certain way, whether an issue was already investigated, what a past session already tried). Append new session-log entries there going forward, not here.

## How to run
```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_reference_data.py
docker compose exec api python scripts/create_superadmin.py
docker compose exec api pytest -v
```

### Testing a school's branded subdomain locally
Every modern browser resolves `*.localhost` to loopback natively (RFC 6761) — no `/etc/hosts` edit, no real DNS, no wildcard TLS needed. Visit `http://<subdomain>.localhost:5173` (e.g. `http://achimota-school.localhost:5173`) and the login page renders that school's logo/name/motto/brand-color/favicon exactly like it would on `<subdomain>.ttek-sms.com` in production — `frontend/src/lib/stores/subdomain.ts`/`hooks.server.ts` already detect `*.localhost` the same way, and the backend's CORS config (`main.py`) explicitly allows it via `allow_origin_regex`. Find (or set) a school's subdomain via Setup > Profile, or check `School.subdomain` directly — every school gets one auto-assigned on creation now (see 12ba).

## Completed phases
- Phase 1 — Core Models + Auth + School Setup (2026-06-11)
- Phase 2 — Academic Structure (2026-06-12)
- Phase 3 — Staff Profiles + Bulk Import (2026-06-12)
- Phase 4 — Students & Enrollment + Bulk Import (2026-06-12)
- Phase 5 — Housing (2026-06-13)
- Phase 6 — Fees (2026-06-13)
- Phase 7 — Report Cards & Documents (2026-06-13)
- Phase 8 — Attendance (2026-06-13)
- Phase 9 — Assessments & Scoring (2026-06-13)
- Phase 10 — Offline Sync (2026-06-13)
- Phase 11 — SMS Notifications (2026-06-13)

## Key decisions log
See blueprint/ttek_sms_blueprint_v4.html for full decisions.
Short version:
- One school = one record (BASIC or SHS, never both)
- Three login types: EMAIL / PHONE / ADMISSION_ID
- 6 seeded StaffPosition templates, 29 permissions across 9 modules
- SchoolCalendar gates attendance — impossible to mark on holiday
- TermEnrollment created by class teacher when student physically reports
- Dexie: WriteOutbox (write queue) — a structured read-side cache was scaffolded early on but never built out and was removed in 12ak; scores are the only entity that goes offline
- Conflict detection via offline_session_started_at on every outbox sync
- YearEndProcess bulk graduation → GraduationRecord per student
- StudentFeeSummary materialized by DB trigger for dashboard performance
- Score.cached_grade_label stored on approval, invalidated on GradingScale change
