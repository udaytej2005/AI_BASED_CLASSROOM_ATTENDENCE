# Smart Classroom Attendance System (AI-based, face recognition)

An academic prototype for recording classroom attendance from an authorised camera, linked to a timetable,
with faculty review and role-based dashboards. It is built as a final-year project.

> **Status: Phases 0–3 implemented and tested; Phase 4 (enrolment and recognition engine) implemented and tested
> with synthetic data.** The backend has accounts and roles, the academic structure and timetable (Asia/Kolkata),
> attendance sessions limited to class periods, consent and face enrolment, and recognition that marks students present
> only after temporal verification. **Not yet validated:** no webcam test, no real students, and no measured recognition
> accuracy. Attendance screens and dashboards (Phases 5–6) are **not built yet**. Browser-level checks are outstanding.
> See [`docs/implementation-status.md`](docs/implementation-status.md) for the full checklist.

> **Responsible use:** Face recognition is probabilistic and can make mistakes. Use it only with consenting volunteers and
> institutional approval. Recognition results are never a basis for disciplinary decisions. Read
> [`docs/known-limitations.md`](docs/known-limitations.md) before any demonstration.

## What is in the repository

| Path | Purpose |
|---|---|
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations (0001–0005), vision package, pytest tests |
| `frontend/` | React + TypeScript + Vite web app, Tailwind CSS, Vitest tests |
| `scripts/check.sh` | Runs all automated checks (lint, types, tests, build, secret hygiene) |
| `data/` | Local-only folder for biometric or personal data (git-ignored; see `data/README.md`) |
| `docs/` | Status, architecture decisions, limitations, installation guide |
| `.env.example` | Template for configuration (placeholders only) |

## Quick start

You need **Python 3.11+**, **Node.js 20+**, and **PostgreSQL 16** (or use the SQLite fallback in the install guide).
Full steps, including Windows PowerShell, are in [`docs/installation-and-troubleshooting.md`](docs/installation-and-troubleshooting.md).

Short version (Linux / macOS):

```bash
# 1. Configure
cp .env.example backend/.env          # then edit DATABASE_URL and set your local password

# 2. Backend
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   # keep this running

# 3. Frontend (second terminal)
cd frontend && npm install && npm run dev                    # open http://localhost:5173
```

Windows (PowerShell, not executed on Windows in the development sandbox; see the install guide for details):

```powershell
Copy-Item .env.example backend\.env
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# second PowerShell window:
cd frontend
npm install
npm run dev
```

### Running the parts

| Part | What it is | Command | Address |
|---|---|---|---|
| Database | PostgreSQL server | Start through the PostgreSQL service | `localhost:5432` |
| Backend API | FastAPI app serving `/api/v1` | `uvicorn app.main:app` in `backend/` | <http://localhost:8000/api/docs> |
| Frontend | Vite dev server; proxies `/api` to the backend | `npm run dev` in `frontend/` | <http://localhost:5173> |
| Camera recognition | Runs inside the backend as a background job, started through the API (`/sessions/{id}/recognition/camera`). It needs a camera reachable from the backend machine (Phase 4; not tested on hardware). | - | - |

Camera runs need the backend to be able to reach the classroom camera (the faculty computer or a server on the
same network). A browser cannot read the camera itself.

### Checks

```bash
./scripts/check.sh
```

Runs backend lint (ruff), type checks (mypy), tests (pytest), frontend type checks (tsc), lint (ESLint), tests (Vitest),
a production build, and a check that no secrets or data files are tracked by Git.

Current results: see `docs/implementation-status.md` (the backend suite passes on SQLite and PostgreSQL 16.2 when
`TEST_DATABASE_URL` is set).

### Creating the first administrator and local demo data

```bash
cd backend && source .venv/bin/activate
python -m app.cli create-admin --email you@example.edu --name "Your Name" --password-stdin   # reads the password from stdin
python -m app.cli seed-demo          # OPTIONAL: synthetic students, faculty and users for local testing only
```

### Face recognition models (Phase 4, optional)

Enrolment and recognition need two model files. They are not stored in Git. Download and verify them once:

```bash
scripts/fetch_face_models.sh     # about 1.1 GB; checks SHA-256 against pinned values
```

Without them, enrolment and recognition return HTTP 503 and the rest of the system still works. Read
[`docs/face-recognition.md`](docs/face-recognition.md) first. It covers consent, retention, limits, and what has not
been measured. Run `python -m app.cli purge-biometrics` on a schedule to delete expired embeddings.

**Demo accounts are local-only.** The seed creates accounts on the `demo.invalid` domain with the documented password
`Demo-Local-2026!` (override with `DEMO_PASSWORD`). **Change or delete them before any real deployment.** Never seed a
database that holds real student records.

## Documentation

- [Implementation status](docs/implementation-status.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [Known limitations](docs/known-limitations.md)
- [Installation and troubleshooting](docs/installation-and-troubleshooting.md)

Planned documentation (from the master prompt) is listed as not started in the implementation status.

## Security and privacy

- Passwords and secrets never belong in code or Git. Use `backend/.env`, which is git-ignored.
- Biometric and personal data stay under `data/` or in the database, and are never committed.
- Sign-in uses Argon2id password hashes and an HTTP-only session cookie. Administrator changes are audited.
- Students can see only their own record. Faculty do not see email addresses. Passwords and tokens never appear in logs.
- Demo accounts are marked as synthetic and must be changed before any real deployment (see above).

## License

No license has been chosen yet. Pretrained face-recognition weights may carry separate, more restrictive licences;
see [`docs/architecture-decisions.md`](docs/architecture-decisions.md) (ADR-004).
