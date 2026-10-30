#!/usr/bin/env sh
# TotalMaint - start locally on macOS / Linux (no Docker needed).
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r backend/requirements.txt
echo "TotalMaint is starting on http://localhost:8000  (Ctrl+C to stop)"
cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
