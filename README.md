# Smart Classroom Attendance System (AI-based, face recognition)

An academic prototype for recording classroom attendance from an authorised camera, linked to a timetable,
with faculty review and role-based dashboards. It is built as a final-year project.

> **Status: Phase 1 (foundation) complete.** The app starts, connects to PostgreSQL, runs migrations, and shows live
> backend and database health. Authentication, students, timetable, face recognition, attendance, and dashboards are
> **not built yet**. See [`docs/implementation-status.md`](docs/implementation-status.md) for the full checklist.

> **Responsible use:** Face recognition is probabilistic and can make mistakes. Use it only with consenting volunteers and
> institutional approval. Recognition results are never a basis for disciplinary decisions. Read
> [`docs/known-limitations.md`](docs/known-limitations.md) before any demonstration.

## What is in the repository

| Path | Purpose |
|---|---|
| `backend/` | FastAPI API, SQLAlchemy models (none yet), Alembic migrations, pytest tests |
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
| Camera / recognition worker | **Not built yet** (Phase 4). It will run on the faculty computer with the webcam. | - | - |

The camera worker will run on the computer that has the webcam, because a browser or a cloud sandbox cannot reliably
reach a classroom camera. It will send only recognition results to the backend.

### Checks

```bash
./scripts/check.sh
```

Runs backend lint (ruff), type checks (mypy), tests (pytest), frontend type checks (tsc), lint (ESLint), tests (Vitest),
a production build, and a check that no secrets or data files are tracked by Git.

Current results (Phase 1): 14 backend tests and 11 frontend tests pass. The backend suite also passes against PostgreSQL
16.2 when `TEST_DATABASE_URL` is set.

## Documentation

- [Implementation status](docs/implementation-status.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [Known limitations](docs/known-limitations.md)
- [Installation and troubleshooting](docs/installation-and-troubleshooting.md)

Planned documentation (from the master prompt) is listed as not started in the implementation status.

## Security and privacy

- Passwords and secrets never belong in code or Git. Use `backend/.env`, which is git-ignored.
- Biometric and personal data stay under `data/` or in the database, and are never committed.
- The API currently exposes only non-sensitive health information. Authentication is the next phase.
- Demo accounts (Phase 2) will be clearly marked and must be changed before any real deployment.

## License

No license has been chosen yet. Pretrained face-recognition weights may carry separate, more restrictive licences;
see [`docs/architecture-decisions.md`](docs/architecture-decisions.md) (ADR-004).
