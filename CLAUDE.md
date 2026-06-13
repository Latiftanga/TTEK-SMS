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
                ├── cache.ts           ← Dexie OfflineCache
                └── outbox.ts          ← Dexie WriteOutbox
```

## Current phase
Phase: 9 — Assessments & Scoring
Status: COMPLETE
Started: 2026-06-13

## Phase 0 checklist
- [x] Folder structure created
- [x] CLAUDE.md written
- [x] .gitignore
- [x] .env.example
- [x] docker-compose.yml
- [x] backend/requirements.txt
- [x] backend/Dockerfile
- [x] backend/app/main.py
- [x] backend/app/core/config.py
- [x] backend/app/core/database.py
- [x] backend/app/core/redis.py
- [x] backend/app/models/base.py
- [x] alembic.ini + alembic/env.py
- [x] frontend/package.json
- [x] frontend/Dockerfile
- [x] .github/workflows/ci.yml
- [ ] Seed data: GhanaRegion, GhanaDistrict, GhanaPublicHoliday
- [ ] Rate limiting middleware
- [ ] ARQ worker setup
- [ ] Sentry integration
- [ ] docker compose up → all services healthy
- [x] pytest passes (4 tests, all green)

## Phase 0 milestone
Docker up. DB migrating. Redis running. ARQ worker processing test job.
Rate limiting active. CI passing. Sentry live. Local storage folder structure created.

## Phase 1 checklist
- [x] All 10 model files (Groups 1–10)
- [x] core/auth.py — JWT + password hashing + token rotation
- [x] core/permissions.py — 3-layer resolution + Redis cache
- [x] schemas/school.py + schemas/auth.py
- [x] services/auth.py + services/school.py
- [x] routers/auth.py + routers/schools.py
- [x] Routers registered in main.py
- [x] alembic/env.py updated to import all models
- [x] scripts/seed_reference_data.py — regions, districts, holidays, positions
- [x] scripts/create_superadmin.py
- [x] tests/test_auth.py (runs in Docker against PostgreSQL)
- [x] docker compose up → alembic upgrade head succeeds
- [x] seed scripts run successfully
- [x] pytest passes (12 tests, all green)

## Phase 1 milestone
All models migrated. Auth endpoints live. Superadmin can log in.
School registration works. Reference data (regions, districts, holidays, positions) seeded.

## How to run
```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_reference_data.py
docker compose exec api python scripts/create_superadmin.py
docker compose exec api pytest -v
```

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

## Phase 6 checklist
- [x] schemas/fees.py — FeeType, FeeStructure, BulkAssignResult, FeeRecordRead, FeeSummaryRead, FeePayment, FeeDiscount (XOR validator), InstalmentPlan
- [x] services/fees.py — fee types, structures, bulk assign, records, summary
- [x] services/fees_payment.py — payments, discounts, instalment plans
- [x] routers/fees.py — 16 endpoints registered
- [x] main.py — fees router included
- [x] alembic migration e5f0a2d91c74 — PostgreSQL trigger for StudentFeeSummary (fires on student_fee_record, fee_payment, fee_discount DML)
- [x] tests/test_fees.py (fee types, structures, bulk assign, records, summary 404)
- [x] tests/test_fees_payment.py (payments, discounts XOR, instalments, summary trigger)

## Phase 6 milestone
Fee types, structures, bulk assignment, payments, discounts, and instalment plans live.
StudentFeeSummary kept in sync by PostgreSQL trigger. Balance computed at read time, never stored.

## Models migration status
All migrations applied through e5f0a2d91c74 (Phase 7 — no new migration needed).

## Phase 7 — Report Cards & Documents (COMPLETE)
Dependency: Phase 6 ✓

Milestone: PDF report cards generated on demand, QR-verified against live data. Documents uploaded and tracked.

Key constraint: Report cards are NEVER stored — generated fresh from Score + Behaviour + Attendance + GradingScale on every request. QR token verifies against live DB, not a cached PDF.

### Checklist
- [x] schemas/assessments.py — BehaviourRecord, ScoreLineRead, ReportCardData, BulkReportRequest, BulkReportJobRead
- [x] schemas/documents.py additions — DocumentRecordRead, ImportBatchResult
- [x] services/behaviour.py — StudentBehaviourRecord CRUD
- [x] services/report_card.py — assemble data (scores + grades + attendance + behaviour + rank)
- [x] templates/report_basic.html — GES Basic format; Jinja2 + @page CSS
- [x] templates/report_shs.html — WASSCE SHS format
- [x] templates/report_ecm.html — ECM Early Childhood milestone template
- [x] services/pdf.py — WeasyPrint render; returns bytes, never writes to disk
- [x] services/qr.py — HMAC-SHA256 token generation + verification
- [x] routers/report_cards.py — GET /report-cards/{enrollment_id}, POST /report-cards/bulk, GET /verify/{token}, GET /report-cards/bulk/{job_id}/download
- [x] services/documents.py — DocumentRecord upload (certificates, letters, photos); local /uploads now → R2 later
- [x] routers/documents.py — upload, list, download, delete
- [x] services/bulk_report_job.py — ARQ background job; generates whole-class PDFs, zips, stores ZIP path
- [x] routers/portal.py — GET /portal/report-cards/{enrollment_id} (ADMISSION_ID login only, gated by Assessment.is_published)
- [x] main.py — report_cards, documents, portal routers registered
- [x] alembic migration — no schema changes needed (StudentBehaviourRecord + DocumentRecord already in models)
- [x] tests/test_report_cards.py — behaviour CRUD, single PDF, invalid format, QR verify/tamper
- [x] tests/test_documents.py — upload, disallowed mime, list, download, delete, wrong-school empty list
- [x] tests/test_portal.py — staff rejected, unpublished 403, published PDF, cross-student 404

### Phase 7 milestone
Report cards rendered on demand by WeasyPrint. QR code on each card verifies live. Bulk class job via ARQ. Documents uploaded and tracked. Parent portal gated by Assessment.is_published.

## Phase 8 — Attendance (COMPLETE)
Dependency: Phase 7 ✓

Milestone: School schedule, calendar generation, daily attendance marking, and per-student summary live.

Key constraint: AttendanceRecord always uses school_calendar_id FK — never a raw date field.
Calendar generation is idempotent; PUBLIC_HOLIDAY beats schedule; default is Mon–Fri if no SchoolSchedule rows.

### Checklist
- [x] schemas/attendance.py — ScheduleUpsert, ScheduleRead, CalendarGenerateRequest, CalendarDayRead, CalendarDayOverride, AttendanceMark, AttendanceMarkRequest, AttendanceRecordRead, AttendanceSummaryRead
- [x] services/attendance_calendar.py — upsert_schedule, list_schedule, generate_calendar (idempotent), list_calendar, override_calendar_day
- [x] services/attendance.py — mark_attendance (SCHOOL_DAY/EXAM_DAY/HALF_DAY gate, upsert), list_attendance, get_summary
- [x] routers/attendance.py — 8 endpoints: schedule CRUD, calendar generate/list/override, mark, records, summary
- [x] main.py — attendance router registered
- [x] tests/test_attendance.py — schedule upsert + idempotent, calendar generate (weekend check) + idempotent, list, override, mark, holiday rejected, re-mark updates, list records, summary

### Business rules enforced
- Cannot mark attendance on PUBLIC_HOLIDAY, WEEKEND, or SCHOOL_HOLIDAY days (422)
- Re-submitting attendance for same student+calendar+period updates the record
- period_id IS NULL for daily (whole-day) attendance

### Phase 8 milestone
School schedule configurable per weekday. Calendar generated idempotently per term with PUBLIC_HOLIDAY beating schedule. Daily attendance marked and re-markable. Per-student term summary with attendance rate.

## Phase 9 — Assessments & Scoring (COMPLETE)
Dependency: Phase 8 ✓

Milestone: Grading scales, assessment types, assessments, and the full score entry → approval flow live.

Key constraints:
- Grade is NEVER stored on Score — resolved at approval time from the school's default GradingScale
- cached_grade_label is set on approval; cleared when GradingScale bands change
- ScoreAuditLog written on every score create/update
- Re-submitting a score resets is_approved=False and clears cached_grade_label

### Checklist
- [x] schemas/assessments.py additions — GradeCreate/Read, GradingScaleCreate/Read, AssessmentTypeCreate/Read, AssessmentCreate/Read, ScoreSubmit, BulkScoreSubmit, ScoreRead, ScoreApproveRequest
- [x] services/grading.py — GradingScale CRUD, Grade band add/delete, resolve_grade(), clear_cached_grades()
- [x] services/assessment.py — AssessmentType CRUD, Assessment CRUD, publish_assessment()
- [x] services/scoring.py — submit_scores (bulk upsert + audit log), approve_scores (resolve grade → cached_grade_label), list_scores
- [x] routers/assessments.py — 13 endpoints; permissions: approve_scores / enter_scores / view
- [x] main.py — assessments router registered
- [x] tests/test_assessments.py — grading scale CRUD, grade band validation, assessment type dedup, assessment create/publish, score submit/range check/resubmit, approve → grade label, list scores

### Permission map
- assessments.approve_scores → grading scale management, assessment type/assessment CRUD, score approval, publish
- assessments.enter_scores → submit scores
- assessments.view → read-only all

### Phase 9 milestone
Teachers enter scores; HODs approve; cached_grade_label set from GradingScale on approval. Report card service already reads cached_grade_label — no changes to Phase 7 code needed.

## Key decisions log
See blueprint/ttek_sms_blueprint_v4.html for full decisions.
Short version:
- One school = one record (BASIC or SHS, never both)
- Three login types: EMAIL / PHONE / ADMISSION_ID
- 6 seeded StaffPosition templates, 29 permissions across 9 modules
- SchoolCalendar gates attendance — impossible to mark on holiday
- TermEnrollment created by class teacher when student physically reports
- Dexie: OfflineCache (structured data) + WriteOutbox (write queue)
- Conflict detection via offline_session_started_at on every outbox sync
- YearEndProcess bulk graduation → GraduationRecord per student
- StudentFeeSummary materialized by DB trigger for dashboard performance
- Score.cached_grade_label stored on approval, invalidated on GradingScale change
