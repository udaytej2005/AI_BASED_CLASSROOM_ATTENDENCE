#!/usr/bin/env bash
# Runs every automated quality gate that is available in this repository.
# Usage: ./scripts/check.sh            (requires backend/.venv and frontend/node_modules)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

step() { printf '\n==> %s\n' "$1"; }

step "Backend: lint"
(cd backend && . .venv/bin/activate && ruff check . && ruff format --check .)

step "Backend: type check"
(cd backend && . .venv/bin/activate && mypy)

step "Backend: tests (SQLite by default; set TEST_DATABASE_URL to test PostgreSQL)"
(cd backend && . .venv/bin/activate && pytest -q)

step "Frontend: type check"
(cd frontend && npm run typecheck)

step "Frontend: lint"
(cd frontend && npm run lint)

step "Frontend: tests"
(cd frontend && npm test)

step "Frontend: production build"
(cd frontend && npm run build)

step "Secret / data hygiene: tracked files that look sensitive"
if git ls-files | grep -E '(^|/)\.env$|\.(db|sqlite3?|pkl|npy|npz|onnx|pt|pth|jpe?g|png)$|^data/' | grep -v '^data/README\.md$'; then
  echo "ERROR: sensitive or data files are tracked by Git." >&2
  exit 1
fi
echo "No sensitive files tracked."

printf '\nAll checks passed.\n'
