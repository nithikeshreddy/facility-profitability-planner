#!/usr/bin/env bash
# Build the single service: the frontend bundle (frontend/dist) and the backend's Python environment.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Building frontend"
(cd frontend && npm ci && npm run build)

echo "==> Installing backend"
if [ ! -x backend/.venv/bin/python ]; then
  "${PYTHON:-python3.11}" -m venv backend/.venv
fi
backend/.venv/bin/pip install --quiet --upgrade pip
backend/.venv/bin/pip install --quiet -r backend/requirements.txt

echo "==> Done. Start with ./start.sh (listens on \$PORT, default 8000)"
