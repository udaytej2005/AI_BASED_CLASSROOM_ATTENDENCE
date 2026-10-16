# Implementation status

Last updated: 2026-10-16 (Phases 0–3 completed; Phase 4 backend implemented and tested with synthetic data. Browser checks for Phases 2–3 and all camera checks are not done.)

Status legend: `Not started` · `In progress` · `Implemented` · `Tested` · `Blocked`

"Tested" means an automated test or a command was run in the development environment and passed. It does **not**
mean the feature was validated with a real webcam, real students, or a real timetable.

## Phase summary (from the master prompt, section 19)

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| 0 | Repository inspection and plan | Tested | Repository contained only `README.md` and no prior work; see the plan below |
| 1 | Project foundation (repo structure, backend/frontend setup, DB config, env handling, health check, UI shell, API connection, dev docs, automated checks) | Tested | `scripts/check.sh`, live check through the Vite proxy to FastAPI and PostgreSQL |
| 2 | Database models, authentication, roles, seed data, student/faculty management, initial-admin setup | Tested | 74 backend tests on SQLite and PostgreSQL 16.2 at the time; 45 frontend unit tests; `scripts/check.sh` passed. Browser-level UI check not done (see below). |
| 3 | Academic configuration, timetable, attendance-session lifecycle | Tested | 111 backend tests on SQLite and PostgreSQL 16.2; ruff and mypy clean. Browser UI for Phase 3 not built or checked. |
| 4 | Enrolment, consent, face-recognition engine, recognition-to-attendance, video upload | Tested (backend, synthetic data) | 175 backend tests (1 skipped) on SQLite and PostgreSQL 16.2 (includes Phase 2–3 tests). Real models: loaded and smoke-tested locally. **Not validated:** no webcam, no real students, no measured accuracy. Frontend pages for enrolment not built. See `face-recognition.md`. |
| 5 | Attendance workflow (live session, temporal confirmation, finalisation, review, audit) | Not started | - |
| 6 | Student, faculty, principal and technical dashboards; reports; CSV export | Not started | - |
| 7 | Security, backend/frontend/integration tests, recognition evaluation | Not started | - |
| 8 | Installation documentation, demo guide, final polish, submission materials | Not started | - |

## Phase 3 detail

| Item | Status | Notes |
|---|---|---|
| Subjects, rooms, classes (generated names), class rosters | Tested | `backend/app/services/structure.py`; duplicates return 409 |
| Cameras: `stream_reference` is a device index, environment-variable name, or file path; raw URLs refused (422) | Tested | Camera references are shown to administrators only |
| Timetable entries in `Asia/Kolkata`; overlap rules for class, faculty and room; breaks | Tested | `backend/app/services/timetable.py`; naive datetimes are treated as UTC |
| Session start only during a scheduled class period; one session per period per date | Tested | `backend/app/services/sessions.py`, `backend/tests/test_timetable_sessions.py` |
| Start, finalise, cancel limited to administrators and the assigned faculty member | Tested | Other faculty receive 403 |
| Migration `0003_academic_timetable_sessions` | Tested | Applied to SQLite and PostgreSQL |
| Browser UI for timetable and sessions | Not started | Planned with the Phase 5 workflow screens |

## Phase 4 detail

| Item | Status | Notes |
|---|---|---|
| Consent records (record, withdraw; withdrawal deletes embeddings) | Tested | `backend/app/services/enrollment.py`, `backend/tests/test_enrollment.py` |
| Enrolment from 5–20 JPEG/PNG photos; one face per photo; quality gates; all-or-nothing minimum | Tested | Synthetic images in tests; rejection reasons per photo |
| Embeddings stored, never returned by any API; re-enrolment replaces | Tested | Response and audit checks in `test_enrollment.py` |
| Retention purge (`python -m app.cli purge-biometrics`, default 365 days) | Tested | Count-only audit record |
| Detector and recogniser adapter (`backend/app/vision/backend.py`) | Tested | Real model path smoke-tested; fake backend for deterministic tests |
| Tracking, matching (cosine 0.363, margin 0.05), `unknown` / `uncertain` / `low_quality` statuses | Tested | `backend/tests/test_vision.py` (25 tests) |
| Temporal verification (5 observations, 2.0 s span, 0.4 s gap) | Tested | Repeated observations in one instant cannot confirm |
| Recognition to attendance: roster-only, once per session, `present` rows | Tested | `backend/tests/test_recognition.py` (16 tests) |
| Camera run and video-upload run as background jobs; one active run per session | Tested (video); **Blocked** (camera) | Camera path needs a real device; the sandbox has none |
| Video upload: type check by file signature, 100 MB cap, deleted after the job | Tested | Lossless synthetic videos (FFV1) through the real decoder |
| Model files: pinned download script with SHA-256 verification | Tested (offline mode, with an archive downloaded separately) | `scripts/fetch_face_models.sh`; hashes match the upstream Git LFS object IDs. The live download path was not run by the script itself. |
| Model licences | Partly verified | MIT (YuNet) and Apache-2.0 (SFace) read from the upstream folders; training-data terms of both are not verified (ADR-009) |
| Recognition accuracy (false accept / false reject / speed) on a separate test set | **Blocked** | Needs consented local data. **No figures are claimed.** |
| Browser / frontend pages for enrolment and recognition | Not started | Backend endpoints only |
| Frontend unit tests for Phase 3–4 pages | Not started | - |

Verification: `pytest` 175 passed, 1 skipped, on SQLite and on PostgreSQL 16.2; `ruff check`, `ruff format --check` and
`mypy` clean. The skipped test needs `FACE_SAMPLE_IMAGE` (see `face-recognition.md`). Counts include Phase 2 and 3 tests.

## Phase 2 detail

| Item | Status | Notes |
|---|---|---|
| Models: users, auth sessions, departments, students, faculty, audit log | Tested | `backend/app/models/`; migration `0002_auth_academic_audit` applied to SQLite and PostgreSQL |
| Password hashing (Argon2id), minimum 12 characters, 3 of 4 character classes | Tested | `backend/app/core/security.py`, `backend/tests/test_auth.py` |
| Sessions: opaque 256-bit token, SHA-256 hash stored, HTTP-only `SameSite=Lax` cookie (`Secure` in production) | Tested | Sessions revoked on deactivation, password reset, and password change by others |
| Login lockout: 5 failures, 15 minutes, stored per account | Tested | Generic error message; trade-off in `known-limitations.md` item 19 |
| Forced password change for admin-created accounts and reset passwords | Tested | Until the change is made, every API call returns 403 except the auth endpoints (current user, change password, sign out) |
| Role-based access control (admin, principal, faculty, student, technical) | Tested | Permission table in `backend/tests/test_rbac.py`; students see only their own record (404 for others) |
| Cross-site request rejection (Origin check on POST/PATCH/PUT/DELETE) | Tested | `backend/app/main.py` middleware |
| Students: create, list, search, filter, update, profile; no hard delete through the API | Tested | Required fields reject explicit `null` with 422 |
| Faculty: create (optionally with login), list, search, update | Tested | Faculty viewers do not see email addresses |
| Departments: create and list (codes normalised, unique) | Tested | Read-only list for all signed-in users |
| User accounts: create, search, filter, activate/deactivate; last active admin protected | Tested | Admin cannot deactivate or demote self |
| Audit records for admin changes (no secrets or biometric fields accepted in details) | Tested | `backend/app/services/audit.py`; list via `/api/v1/audit` |
| Synthetic seed data (3 departments, 3 faculty, 20 students, 26 users), clearly labelled local-only | Tested | `python -m app.cli seed-demo`; second run is a no-op. Demo password must be changed before any deployment. |
| Initial admin setup from the command line | Tested | `python -m app.cli create-admin --password-stdin` (password is never a command-line argument) |
| Frontend: sign-in, sign-out, change-password page, guarded routes, 403 page | Tested (unit) | `frontend/tests/guards.test.tsx`, `LoginPage.test.tsx`, `ChangePasswordPage.test.tsx` |
| Frontend: role-filtered navigation and role-aware dashboard | Tested (unit) | `navigation.test.tsx`, `DashboardPage.test.tsx` |
| Frontend: students, student detail/profile, student form, faculty list and form, user accounts | Tested (unit) | Mocked `fetch`; not checked in a real browser |
| Frontend: system-health page restricted to administrators and technical operators | Tested (unit) | `App.test.tsx` |
| Browser check of every new page (rendering, keyboard use, screen-reader labels) | Not started | Planned for Phase 7 with end-to-end tests |
| Docker / docker-compose | Not started | Docker is not available in the sandbox |

## Phase 0 plan (as executed)

1. Inspected the repository. Only `README.md` existed on `main` (commit `50f014f`). No `docs/`, code, tests, or
   tracking documents existed, so there was no existing work to preserve or repair.
2. Read the uploaded PRD (`Smart_Classroom_Attendance_PRD (2).pdf`, 8 pages). Its key requirements are reflected in
   the master-prompt requirements and in the status tables below.
3. Confirmed the local toolchain: Node 22, npm 10, Python 3.11, Git 2.39, gh 2.23. Docker and PostgreSQL were not
   installed and could not be installed through apt. A PyPI-packaged PostgreSQL binary (`pgserver`) was used
   **only for verification in the sandbox**; it is not a project dependency.
4. Chose the stack (ADR-001 to ADR-003) and sequenced the remaining phases as listed above.

## Phase 1 detail

| Item | Status | Notes |
|---|---|---|
| Repository structure (`backend/`, `frontend/`, `scripts/`, `data/`, `docs/`) | Tested | `data/` holds only a README; real data is git-ignored |
| Backend: FastAPI app factory, versioned router `/api/v1` | Tested | `backend/app/main.py`, `backend/app/api/v1/` |
| Backend: settings from environment (`pydantic-settings`), production safety checks | Tested | `backend/app/core/config.py`, 6 tests |
| Backend: SQLAlchemy engine/session, naming conventions, `check_database()` | Tested | `backend/app/db/` |
| Backend: Alembic configured, baseline revision `0001` | Tested | Applied to a clean SQLite file (automated test) and to a clean PostgreSQL 16.2 database (manual run in the sandbox) |
| Backend: health endpoints (`/health`, `/health/database`) | Tested | Database check never reveals connection strings |
| Backend: CORS allow-list and request-size limit (413) | Tested | `backend/tests/test_health.py`; API docs hidden in production (tested) |
| Backend: lint (ruff), type check (mypy), tests (pytest) | Tested | 14 tests passing on SQLite and on PostgreSQL |
| Frontend: Vite + React 18 + TypeScript, Tailwind CSS v4 | Tested | Production build succeeds |
| Frontend: routing (React Router), not-found page | Tested | `frontend/tests/App.test.tsx` |
| Frontend: app shell (sidebar, top bar, breadcrumbs, skip link, demo-data banner) | Tested | Unavailable pages are disabled and labelled "Planned", not dead links |
| Frontend: typed API client with error mapping | Tested | `frontend/tests/apiClient.test.ts` |
| Frontend: live health dashboard and system-health page | Tested | Unit tests mock `fetch`; the live path was checked through the running dev proxy |
| Frontend: lint (ESLint), type check (tsc), tests (Vitest) | Tested | 11 tests passing |
| Root tooling: `.gitignore`, `.env.example`, `scripts/check.sh` | Tested | `check.sh` runs every gate and a tracked-secret/data hygiene check |
| Documentation: README, status, decisions, limitations, installation | Implemented | Windows PowerShell commands are written but were **not executed** on Windows in this environment |
| Docker / docker-compose | Not started | Docker is not available in the sandbox; deferred until it can be tested |

## Requirement traceability (PRD and master prompt)

Only the rows marked Tested have working, verified implementations.

| Requirement | Status |
|---|---|
| Student records (ID, name, roll number, department, year, section, status) | Tested (Phase 2). Roll-number field is the student code. |
| Face enrollment with quality checks and embeddings | Tested (backend, Phase 4). No enrolment screen yet. |
| Face detection, tracking, recognition (`recognized_candidate`/`unknown`/`uncertain`/`low_quality`/`error`) | Tested (backend, Phase 4). Accuracy not measured. |
| Timetable with `Asia/Kolkata` timezone and active-period resolution | Tested (Phase 3) |
| Attendance sessions, temporal confirmation, duplicate prevention, absentees from roster | Partly: sessions and temporal confirmation and duplicate prevention Tested (Phases 3–4). Absentee list and corrections Not started (Phase 5). |
| Authentication (hashed passwords) and role-based access control | Tested (Phase 2) |
| Student / faculty / principal / technical dashboards | Partly implemented: role-aware home page with directory counts and a student summary (Phase 2). Attendance dashboards are Phase 6. |
| CSV exports and reports | Not started (Phase 6) |
| Audit logs | Tested for admin changes (Phase 2). Attendance and enrollment events come later. |
| Synthetic demo seed (20 students etc.) | Tested (Phase 2) |
| Recognition evaluation on separate test set | Blocked: needs consented local data. No figures claimed. |
| Documentation set (`docs/` list in master prompt section 17) | Partly started. Status, decisions, limitations, installation and `face-recognition.md` exist. |

## Next phase

Phase 5 (attendance workflow: live session view, absentee list from the roster, manual corrections with audit, session
finalisation review). Before Phase 5 starts: run the Phase 2–4 pages in a real browser (`known-limitations.md` item 18),
confirm the attendance rules (item 21), and decide how the Phase 4 recognition runs are started from the interface.
