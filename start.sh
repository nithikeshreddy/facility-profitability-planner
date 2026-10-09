#!/usr/bin/env bash
# Production start: FastAPI serves /api/* and the built frontend on $PORT.
# One worker on purpose: SQLite, seed-on-startup and one shared demo state.
set -euo pipefail
cd "$(dirname "$0")/backend"

UVICORN=uvicorn
if [ -x .venv/bin/uvicorn ]; then
  UVICORN=.venv/bin/uvicorn
fi
exec "$UVICORN" app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
