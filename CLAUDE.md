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
Phase: 12 — Frontend Build
Status: IN PROGRESS
Started: 2026-06-13

### Phase 12 sub-phases completed
- 12a–c: SvelteKit foundation, PWA manifest, axios client, login flow, app shell, role-adaptive dashboard
- 12d: Multi-tenant subdomain detection, custom domain support, branded login, TopBar user menu
- 12e: Academic Setup (/admin/academic), Classes & Subjects (/admin/structure), Staff directory + detail (/admin/staff)
- 12f: Class detail page with card header, tabs (students/subjects/teachers), academic sidebar nav
- 12g: School Setup page (/admin/setup) — Profile, Subjects, Programmes, SMS, Email tabs; GET/PATCH /schools/me + /schools/me/logo backend endpoints; EmailConfig + EmailLog models + migration h6i7j8k9l0m1; email router; SMS Config moved from sidebar into Setup; Subjects/Programmes removed from Academic sub-nav
- 12h: Students module hardening — students.py split into students.py/students_enrollment.py/students_lifecycle.py/students_detail.py (300-line rule, students_detail's /{student_id} registered last in main.py to avoid path capture); admission_number auto-generation ({SCHOOL_CODE}/{YEAR}/{SEQ}, resets yearly, optional on create); primary-guardian invariant enforced on add/update/remove guardian (first guardian forced primary, last guardian can't be removed, primary removal auto-promotes, sole-primary demotion blocked); student photo wired end-to-end (POST/DELETE /students/{id}/photo, image pipeline in storage.py shared with school logo upload, PhotoAvatar.svelte); test coverage added for update_guardian, portal access grant/revoke, and all of the above (269 backend tests passing)
- 12i: Fee gate for term enrollment — AcademicTerm.block_owing_students toggle (+ set_by/set_at audit fields, migration f6a7b8c9d0e1) gates create_term_enrollment against the student's live StudentFeeSummary balance (never cached); waiver via TermEnrollmentCreate.fee_waiver_reason, honoured only if the caller's resolved permissions include fees.manage; bulk_term_enrollment skips fee-blocked students like it already did duplicates. Frontend: fee-gate toggle in admin/academic TermsSection, inline waiver form on EnrollmentTab's Register button, "Fee waived" badge on TermRegistrationRow, enrolled-vs-skipped counts in BulkActionModal's toast. Found and fixed a real bug during this work: bulk_term_enrollment's skip-on-duplicate path used a bare db.rollback(), which rolls back the whole session transaction (not just the failed item) — now each item runs in its own db.begin_nested() savepoint, matching register_subjects/student_import/staff_import/housing/promotion. Deliberately deferred: the instalment-plan "on schedule" carve-out (FeeInstalmentPlan.is_paid is never set anywhere in this codebase, so it would be a dead branch). 277 backend tests passing.
- 12j: Parent/student portal — the report-card viewing flow itself (scoring → approval → publish → PDF) was already solid and tested, but there was no way for a parent to actually reach it: an ADMISSION_ID login redirected to /dashboard same as staff, which silently rendered a blank teacher view for anyone without a staff_member_id, and there was no self-service endpoint for a portal user to discover their own name/class/enrollment_id. Added GET /portal/me + GET /portal/term-enrollments (schemas/portal.py, services/portal.py — is_report_published extracted and shared with the existing report-card endpoint). Frontend: new (portal) route group with its own minimal layout at /portal — profile card, per-term published/not-yet-published state, "View report card" opens the PDF (same blob pattern as the existing staff reports page); login redirects ADMISSION_ID users to /portal instead of /dashboard; (app) layout redirects a portal user away if they land on a staff route anyway. Verified live end-to-end: real student, granted portal access, logged in, confirmed is_published flips after staff publish an assessment, confirmed the PDF is retrievable. 8 new backend tests, 285 total passing; svelte-check 0 errors.
- 12k: Fee balance in the parent portal — GET /portal/term-enrollments now also returns fee_total_due/fee_total_paid/fee_balance/fee_last_payment_date per term, computed live from StudentFeeSummary (never cached; null when no fees assigned yet, not a zero balance) — folded into the existing term list rather than a new endpoint. Frontend: each term row on /portal shows "Balance due: GHS X" (red) or "Fees fully paid" (green) using the same ghs() formatter as the staff fees pages. Verified live: created a fee structure, bulk-assigned it, confirmed the portal showed the full balance, recorded a partial payment as staff, confirmed the portal balance updated live (600 → 350). 9 portal tests passing, 285 backend tests overall.
- 12l: Term results lock + behaviour audit trail — rejected calendar-day-type gating for scores/behaviour (would block legitimate Saturday classes, boarding incidents on holidays, etc.) in favour of workflow-state locking, matching the existing Assessment.is_published pattern. Added AcademicTerm.results_locked (+ results_locked_by_id/results_locked_at, mirroring the block_owing_students pattern from 12i; migration b1c2d3e4f5a6) which freezes submit_scores/approve_scores and behaviour record create/delete for every assessment in that term, independent of each Assessment's own is_published flag. Override requires assessments.approve_scores + a non-blank override_reason, written to ScoreAuditLog.reason (scores) or the new BehaviourAuditLog (behaviour — previously had no audit trail at all; SET NULL, not CASCADE, on the record FK so the log survives a delete). Added core/permissions.py::user_has_permission() (User → staff_member_id → resolve_permissions, mirroring student_enrollment.py's fee-waiver check) since submit_scores is gated at the router on the weaker enter_scores permission and needs to check for the stronger one internally. Also added a light term-bounds sanity check — Assessment.due_date and StudentBehaviourRecord.incident_date must fall within the enclosing academic_term's start_date–end_date — deliberately not calendar-day-type validation. 14 new tests (test_scoring_lock.py, test_behaviour_lock.py), 299 backend tests overall. Frontend: initially put the "Results lock" toggle next to "Fee gate" in admin/academic TermsSection, then relocated it to the /assessments list page (next to the class/term filters) — /admin/academic is roles:['admin']-only in nav.ts, but the override permission (assessments.approve_scores) maps to the 'approver' role (HOD/Exam Officer) who can't see that page at all; /assessments is already visible to teacher/admin/approver and is where the term-scoped workflow this lock belongs to actually happens. TermsSection keeps a read-only "Results locked" badge (points to Assessments to manage it) but no toggle, to avoid two controls for one piece of state. The assessment detail page shows a "Term locked" badge and, if Save/Approve gets a 423, opens the new reusable OverrideReasonModal to collect a reason and retry — extracted AssessmentActionsBar out of that page to stay under the 300-line cap while adding the logic. Verified live against the running stack: locked a term via PATCH (both from TermsSection and later from the /assessments toggle), confirmed submit/approve scores 423 without a reason and succeed with one, confirmed ScoreAuditLog.reason captured the override text; svelte-check 0 new errors.
- 12m: Behaviour records management page — the backend endpoints (POST/GET/DELETE /behaviour) existed since Phase 9 but had no frontend at all. Added new BehaviourTab on the student detail page (students/[id], alongside Profile/Guardians/Enrollment/Fees/Medical) rather than a class-wide list like /assessments, since incidents are logged one at a time against a specific student as they happen — term selector + "Log incident" form + list, mirroring FeesTab's term-selector pattern; reused OverrideReasonModal and ConfirmModal for the results_locked create/delete flow (create/delete both require assessments.approve_scores per the router, so only canManage = admin/approver sees the button and any 423 is purely "missing reason", never "missing permission"). Found the same nav mismatch as 12l: the top-level "Students" nav item was roles:['teacher','admin'] only, even though HOD/Exam Officer (the 'approver' role) already holds students.view/edit + assessments.approve_scores at the backend — added 'approver' to that one nav entry (children Transfers/Promotions/Graduation stay admin-only, unrelated to this permission). New frontend/src/lib/api/behaviour.ts API client. Verified live: created and deleted a behaviour record through the real endpoints, confirmed SSR of /students and /students/[id] still 200, svelte-check 0 new errors (only pre-existing @apply warnings, same pattern as every other tab file).
- 12n: Term lock extended to assessment edit/delete + AssessmentAuditLog — 12l's AcademicTerm.results_locked freeze only covered scoring/behaviour; update_assessment and delete_assessment could still mutate a locked term's assessments untouched. Promoted scoring.py's private _term_lock_override_reason into core/permissions.py::check_term_lock_override() so assessment.py could reuse it: update_assessment now needs the same assessments.approve_scores + non-blank override_reason to edit a locked term's assessment; delete_assessment has no override path at all (deleting one permanently removes its scores and their audit trail, so there's no safe "undo" to gate). A code review of this in-flight work caught a real bug: update_assessment validated the override_reason via check_term_lock_override() but then discarded the return value — no audit table existed for assessment field edits at all, unlike ScoreAuditLog/BehaviourAuditLog. Added AssessmentAuditLog (migration c2d3e4f5a6b7) — every name/max_score/due_date edit is logged with an old/new value snapshot, reason populated only on a locked-term override; SET NULL (not CASCADE) on the assessment FK so the log survives a delete. Frontend: the assessment detail page's edit form now goes through the same OverrideReasonModal flow as submit/approve. Verified live against the running stack (PATCH with/without override, confirmed audit rows and reason capture via direct DB query, confirmed the row survives assessment delete with assessment_id set to NULL); 359 backend tests passing overall.
- 12o: Guardian portal login (schema foundation) — added User.guardian_id (PHONE login type; a guardian can be linked to multiple children via StudentGuardian, so one account spans multiple students, unlike student_id's one-to-one) alongside staff_member_id/student_id, migration a8b9c0d1e2f3. The same migration retroactively created ck_user_admission_id_matches_login_type and a widened three-way ck_user_single_identity, both of which existed only in the SQLAlchemy model's __table_args__ since the Phase 1 baseline and were never actually applied to the database. Login/session wiring for the guardian PHONE flow itself is not yet built — this is the schema step only. While reviewing the notification path for the new portal type, found student_portal.py's _notify_guardian silently always failed: it imported a function that doesn't exist (sms_notifications.get_active_driver — the real name is _get_active_driver) and called _log_result with the wrong argument order, both swallowed by a broad except Exception. Fixed by routing the student ADMISSION_ID portal's notification through a new shared notify_portal_access() helper, built so the future guardian PHONE portal can reuse it too. Known limitation (documented on the model): phone is globally unique platform-wide like email, so a guardian with children at two different schools on this platform can't hold two separate guardian portal accounts under the same phone number — not solved, rare in practice, same constraint already applies to staff PHONE accounts.
- 12p: Two standalone fixes, unrelated to each other and to 12o's in-flight guardian-portal work. (1) Housemaster dashboard only ever showed one house: assign_house_master() (services/housing.py) deactivates the *previous* housemaster of the house being assigned but never checks whether the incoming staff member already runs a different house, so a staff member active as HouseMaster for two houses at once (same bug shape as TeacherDashboard's former my_class) had the second silently dropped. HousemasterDashboard.house_id/house_name/... (singular) replaced with my_houses: list[HouseSnapshot]; extracted services/dashboard_housemaster.py (dashboard.py was approaching the 300-line cap) mirroring the existing dashboard_admin.py/dashboard_teacher.py split. (2) Report cards couldn't actually be scanned: qrcode[pil] has been in requirements.txt since Phase 7 but nothing ever imported it — all three templates (basic/SHS/ECM) only printed the literal text "Verify: /verify/{token}". Added services/qr.py::generate_qr_image() (PNG data URI encoding {app_base_url}/verify/{token}) wired into report_card.py's context; templates now embed the image above the existing verify text. Verified live against the running stack: real TermEnrollment → assembled context → WeasyPrint-rendered PDF, confirmed the embedded PNG decodes and verify_token() round-trips it to the correct enrollment_id/school_id. 359 backend tests passing, svelte-check 0 new errors.
- 12q: Subject-registration eligibility for scoring — prompted by a report that a prior system auto-enrolled every class member in every subject assigned to the class, so electives (e.g. French vs Literature-in-French in the same class) silently got mixed up. A critical read of this codebase found the same failure mode one layer down: SubjectRegistration (per-student, per-term, added in 12i's EnrollmentTab) was recorded but never consulted anywhere — create_assessment didn't check subject_id belonged to the class, the assessment detail page's score-entry roster pulled listStudents({class_id}) with no subject filter at all, and submit_scores accepted any student_id in the payload. Fixed all three: create_assessment now requires subject_id to be an active ClassSubject on class_id; new GET /assessments/{id}/roster (services/subject_roster.py) returns only students eligible for the assessment's subject, and the assessment detail page now calls it instead of the plain class-wide student list; submit_scores rejects (422, naming the students) anyone not registered for that subject this term. Eligibility rule is deliberately backward-compatible: a student's registration only becomes authoritative once at least one SubjectRegistration row exists for their TermEnrollment that term — absence of registration data (no TermEnrollment yet, or one with nothing registered) falls back to "the whole class curriculum applies", so schools that never use subject registration (GES Basic, no electives) are unaffected; the entire pre-existing test suite passed unchanged with zero fixture changes beyond one (test_assessments.py's subject fixture needed a ClassSubject row to keep passing the new create_assessment guard). Split AssessmentType CRUD out of services/assessment.py into services/assessment_type.py first, to stay under the 300-line cap while adding the ClassSubject check. New test_subject_roster.py (5 tests) covers the elective-split scenario directly. 364 backend tests passing, svelte-check 0 new errors.
- 12r: Guardian portal login — completes 12o's schema-only User.guardian_id groundwork with the actual PHONE login flow and self-service portal. A guardian can be linked to multiple children via StudentGuardian, so this is a different shape from the student ADMISSION_ID portal (single implicit self): new services/guardian_portal.py grants/revokes portal access from a student's Guardians tab; unlike a student's admission number, a guardian has no safe predictable initial password, so grant_portal_access sets a random unusable one and SMS's the guardian to use "Forgot password?" with their own phone number — reuses the existing OTP reset flow (services/auth_reset.py) completely unchanged, no new onboarding-password mechanism needed. New GET /portal/children (guardian-only) lists linked students; the existing GET /portal/term-enrollments and GET /portal/report-cards/{id} now accept an optional student_id, required and StudentGuardian-verified for a guardian caller, ignored (resolves to self) for a student's own login — unchanged behaviour there. UserRead/frontend CurrentUser gained guardian_id, since PHONE login is shared with staff accounts and login_type alone can't tell the frontend whether to route to /portal or /dashboard. Guardian.phone doubles as the portal login identifier, so update_guardian now keeps an active portal account's User.phone in sync with edits, and both grant and update surface a clean 409 (not a raw 500) on the platform-wide phone-uniqueness collision documented as a known limitation since 12o. Frontend: GuardianPortalAccessButton on each guardian row; /portal shows a child switcher for guardians with 2+ children, unchanged single-profile view for one child or a student login (the two portal-read queries needed reactiveQuery() rather than plain createQuery({...}) since they gate on $currentUser, which hydrates asynchronously after mount — caught this in my own first draft before it shipped). 13 new backend tests (test_guardian_portal.py), 377 backend tests passing overall, svelte-check 0 new errors. Known remaining gaps, not addressed here: services/student.py is pre-existing debt at ~510 lines (over the 300-line cap, untouched since it was tangential to this feature); ranking (services/report_card.py::_compute_rank) still isn't elective-aware (flagged in 12q, a design decision deferred, not a clear bug).

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
- Phase 10 — Offline Sync (2026-06-13)
- Phase 11 — SMS Notifications (2026-06-13)

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

## Phase 10 — Offline Sync (COMPLETE)
Dependency: Phase 9 ✓

Milestone: Dexie WriteOutbox items processed server-side; concurrent edit conflicts detected, logged, and resolvable.

Key constraint: offline_session_started_at is sent with every outbox item. If Score.submitted_at > offline_session_started_at, the server received a newer write after the session started → OfflineSyncConflict written.

### Checklist
- [x] schemas/sync.py — OutboxScoreData, OutboxItem, OutboxSyncRequest, OutboxItemResult, ConflictRead, ConflictResolveRequest
- [x] services/sync.py — process_outbox (per-item score sync with conflict check), list_conflicts (user-scoped, unresolved only), resolve_conflict (CLIENT_WINS re-applies; SERVER_WINS/DISCARDED mark resolved; MERGED applies merged_data)
- [x] routers/sync.py — POST /sync/outbox, GET /sync/conflicts, POST /sync/conflicts/{id}/resolve
- [x] main.py — sync router registered
- [x] tests/test_sync.py — new score applied, server-older applied, conflict detected, list empty + shows unresolved
- [x] tests/test_sync_resolve.py — SERVER_WINS, CLIENT_WINS (verifies score updated), DISCARDED, double-resolve 409

### Conflict resolution actions
- CLIENT_WINS → re-applies client score via _apply_score; writes ScoreAuditLog
- SERVER_WINS / DISCARDED → marks resolved; server data unchanged
- MERGED → applies caller-supplied merged_data score

### Phase 10 milestone
Offline score submissions safely merged. Conflicts surfaced to the teacher for manual resolution. Double-resolve rejected with 409.

## Phase 11 — SMS Notifications (COMPLETE)
Dependency: Phase 10 ✓

Milestone: Per-school SMS provider selection, credential management, automatic parent notifications, and manual send live.

Key design: Each school independently chooses and configures its SMS provider. Only one provider is active at a time. Activating a new provider deactivates all others automatically.

### Architecture
- SmsDriver ABC + 5 concrete drivers (AfricasTalking, Hubtel, Arkesel, WiGal, Twilio) in services/sms_driver.py
- Credentials: api_key (always required) + api_secret (where needed per provider) — stored in sms_config table, never returned by any GET endpoint
- Phone normalization: Ghana 0XXXXXXXXX → +233XXXXXXXXX (E.164 format)
- SmsLog table: every send attempt logged with status, error, entity_type/entity_id for traceability
- Fire-and-forget pattern: notification functions catch all exceptions — SMS failure never rolls back a fee payment, attendance mark, or assessment publish

### Checklist
- [x] models/school.py — SmsStatus enum + SmsLog model added
- [x] alembic/versions/a3f9c1e87b20 — sms_log table migration
- [x] services/sms_driver.py — SmsDriver ABC, SmsResult, 5 drivers, _normalize_phone(), build_driver() factory
- [x] services/sms_notifications.py — get_active_driver(), _primary_guardian_phone(), _log_result(), notify_fee_receipt(), notify_attendance_absent(), notify_report_published(), send_manual()
- [x] services/school_config.py — list_sms_configs(), activate_sms_provider() (deactivates others), delete_sms_config()
- [x] schemas/sms.py — SmsActivateRequest, SmsSendRequest (160-char validator), SmsSendResult, SmsSendResponse, SmsLogRead
- [x] routers/sms.py — 6 endpoints: POST/GET configs, POST activate, DELETE config, POST send, GET logs
- [x] services/fees_payment.py — notify_fee_receipt() wired after record_payment() flush
- [x] services/attendance.py — notify_attendance_absent() wired for ABSENT marks
- [x] services/assessment.py — notify_report_published() to all enrolled students on publish
- [x] main.py — sms router registered
- [x] tests/test_sms.py — phone normalization, config CRUD, activate (only one active), delete, send-no-config 503, message >160 chars 422, send-with-mock, log endpoint

### Automatic notification triggers
- Fee receipt: fires after services/fees_payment.py::record_payment() → primary guardian
- Absence alert: fires in services/attendance.py::mark_attendance() for ABSENT status → primary guardian
- Report published: fires in services/assessment.py::publish_assessment() → all enrolled students' primary guardians

### Provider credential fields
| Provider        | api_key           | api_secret       | sender_id      |
|-----------------|-------------------|------------------|----------------|
| AFRICAS_TALKING | AT API key        | AT username      | Sender name    |
| HUBTEL          | Client ID         | Client secret    | Sender name    |
| ARKESEL         | Arkesel API key   | (not used)       | Sender name    |
| WIGAL           | WiGal API key     | (not used)       | Sender name    |
| TWILIO          | Account SID       | Auth Token       | E.164 number   |

### Phase 11 milestone
Each school picks and configures its own SMS provider. Credentials stored server-side and never exposed via API. Automatic notifications fire on fee payments, absences, and report card publishing. Full audit trail in sms_log. Manual send available to school HEAD via POST /sms/send.

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
