# Facility Profitability Planner

Prototype for the abrightlab 2,000-Location Challenge: open a loss-making location, inspect the evidence, compare fixes, check costs and feasibility, and save a proposed action. All data is synthetic demonstration data.

Spec: [docs/SPEC.md](docs/SPEC.md) · Working notes for Claude Code: [CLAUDE.md](CLAUDE.md)

## Prerequisites

- Python 3.11+
- Node 20+

## Backend (FastAPI, port 8000)

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Check it: `curl localhost:8000/api/health`. The SQLite database is created at `backend/facility.db` (set `DATABASE_URL` to override).

Run tests:

```bash
cd backend
.venv/bin/pytest
```

## Frontend (Vite, port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Requests to `/api/*` are proxied to the backend on port 8000, so start the backend first.

`npm run build` writes `frontend/dist`, which the backend serves at `/` when present (single-service deploy).
