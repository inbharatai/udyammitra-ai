#!/usr/bin/env bash
# Run both backend and frontend for local dev (macOS/Linux/Git Bash).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/backend/.venv/bin/python"
[ -x "$PY" ] || PY="$ROOT/backend/.venv/Scripts/python.exe"

trap 'kill 0' EXIT INT TERM
( cd "$ROOT/backend"  && "$PY" -m uvicorn app.main:app --reload --port 8000 ) &
( cd "$ROOT/frontend" && npm run dev ) &
wait