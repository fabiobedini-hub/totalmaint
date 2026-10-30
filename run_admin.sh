#!/usr/bin/env sh
# TotalMant Admin - the console for the server's administrator, locally on macOS / Linux.
# Start ./run_local.sh first (it prepares the database), then this one in a second terminal.
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run ./run_local.sh once first"; exit 1; }
. .venv/bin/activate
if [ -z "$ADMIN_PASSWORD" ] && ! grep -qE '^ADMIN_PASSWORD=.{10,}' .env 2>/dev/null; then
    echo "ADMIN_PASSWORD is not set. For a local test it is: admin-locale-123"
    export ADMIN_PASSWORD=admin-locale-123
fi
echo "TotalMant Admin is starting on http://localhost:8001  (Ctrl+C to stop)"
cd backend
exec python -m uvicorn app.admin_main:app --host 127.0.0.1 --port 8001 --reload --reload-dir app
