# Installation and troubleshooting

This guide covers the Phase 1 foundation: backend API, PostgreSQL database, and frontend dev server.
Camera and face-recognition setup will be added in Phase 4.

> **Verification note:** The Linux commands were executed end-to-end in the development sandbox (Debian 12). The Windows
> PowerShell commands follow the same steps but were **not executed on Windows** in that environment. If a step fails,
> please report it.

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.11 or newer (3.11 tested) | `python --version` (Windows: `py -3.11 --version`) |
| Node.js | 20 or newer (22 tested) | `node --version` |
| npm | comes with Node.js | `npm --version` |
| PostgreSQL | 16 recommended (16.2 tested in the sandbox) | `psql --version` |
| Git | any recent version | `git --version` |

Docker is **not** required and is not yet provided.

## 2. Get the code

```powershell
git clone https://github.com/udaytej2005/AI_BASED_CLASSROOM_ATTENDENCE.git
cd AI_BASED_CLASSROOM_ATTENDENCE
git checkout arena/cecca541-ai-based-classroom-attendence
```

## 3. Create the database (PostgreSQL)

Use a password you choose. Do **not** reuse the placeholder `change-me` on a shared computer.

Windows (PowerShell, with PostgreSQL's `bin` folder on `PATH`):

```powershell
psql -U postgres -c "CREATE USER attendance WITH PASSWORD 'choose-a-local-password';"
psql -U postgres -c "CREATE DATABASE attendance OWNER attendance;"
```

Linux / macOS:

```bash
sudo -u postgres psql -c "CREATE USER attendance WITH PASSWORD 'choose-a-local-password';"
sudo -u postgres psql -c "CREATE DATABASE attendance OWNER attendance;"
```

## 4. Configure the backend

Copy the template to `backend/.env`. The backend reads this file from the `backend/` folder. **Never commit `.env`.**

Windows:

```powershell
Copy-Item .env.example backend\.env
notepad backend\.env   # set DATABASE_URL to match step 3
```

Linux / macOS:

```bash
cp .env.example backend/.env
nano backend/.env
```

Set `DATABASE_URL` to, for example:

```text
postgresql+psycopg://attendance:choose-a-local-password@localhost:5432/attendance
```

## 5. Install and migrate the backend

Windows (PowerShell):

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
alembic upgrade head
```

Linux / macOS:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
alembic upgrade head
```

`alembic upgrade head` creates the migration history table. The baseline revision is empty, so no business tables exist yet.

## 6. Start the backend

From `backend/` with the virtual environment active:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Check it:

- Health: <http://localhost:8000/api/v1/health>
- Database health: <http://localhost:8000/api/v1/health/database>
- API documentation: <http://localhost:8000/api/docs>

## 7. Install and start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dashboard calls `/api/v1/health` through the Vite proxy, which forwards it to
`http://127.0.0.1:8000` by default. Set `API_PROXY_TARGET` in the environment if your backend runs elsewhere.

## 8. Run all checks

From the repository root (Linux / macOS, or Git Bash on Windows):

```bash
./scripts/check.sh
```

This runs backend lint, type checks, tests, frontend type checks, lint, tests, a production build, and a check that no
sensitive files are tracked by Git.

To run backend tests against PostgreSQL instead of SQLite:

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://attendance:choose-a-local-password@localhost:5432/attendance_test'
pytest -q
```

Create `attendance_test` first, owned by the `attendance` user.

## 9. Stop the application

Press `Ctrl+C` in the backend and frontend terminals. To deactivate the Python environment, run `deactivate`.

## 10. Where local data lives

| Item | Location | Committed to Git? |
|---|---|---|
| Configuration and secrets | `backend/.env` | No (ignored) |
| Database contents | PostgreSQL server (your local data directory) | No |
| Biometric data, exports (later phases) | `data/` | No (ignored) |
| Python packages | `backend/.venv/` | No (ignored) |
| Frontend packages | `frontend/node_modules/` | No (ignored) |

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard says "The backend is not reachable" | Backend is not running, or is on another port | Start uvicorn (step 6). Check port 8000. |
| Database shows "unreachable" but the API runs | Wrong `DATABASE_URL`, or PostgreSQL is stopped | Check the URL and password. Start the PostgreSQL service. |
| `password authentication failed` | Password in `.env` differs from the one set in PostgreSQL | Re-run `ALTER USER attendance WITH PASSWORD '...'` and update `.env`. |
| `ModuleNotFoundError` | Virtual environment not active, or packages not installed | Activate `.venv` and run `pip install -r requirements-dev.txt`. |
| `Unknown IANA timezone` on startup | `TIMEZONE` is misspelled | Use a name such as `Asia/Kolkata`. |
| `SECRET_KEY must be set ... in production` | `APP_ENV=production` with the default key | Generate a key (see `.env.example`) or set `APP_ENV=development` locally. |
| `npm run dev` fails with port in use | Another process is on 5173 | Stop it, or run `npm run dev -- --port 5174`. |
| PowerShell says scripts are disabled | Execution policy blocks `Activate.ps1` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry. |
| `alembic upgrade head` fails on a fresh machine | Database user lacks rights | Make `attendance` the owner of the database (step 3). |

### SQLite fallback (only if PostgreSQL cannot be installed)

Set this in `backend/.env` and run the migrations again:

```text
DATABASE_URL=sqlite:///./../data/attendance.db
```

SQLite is a development fallback. The intended database is PostgreSQL, and some PostgreSQL behaviour is not identical in
SQLite. Record any use of the fallback in your report.
