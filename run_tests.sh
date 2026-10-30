#!/usr/bin/env sh
# TotalMaint - run the automatic tests (temporary database, never your real data).
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install --quiet -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
exec python -m pytest "$@"
