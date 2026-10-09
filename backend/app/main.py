import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app import models
from app.db import DB_FILE, Base, SessionLocal, engine
from app.routers import actions, demo, health, locations, overview, renewals, vendors
from app.seed import reset_and_seed

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(models.Location)) == 0
    if empty:
        # A fresh deploy (missing or empty database) starts with the demonstration data.
        summary = reset_and_seed()
        log.info("Seeded demonstration data into %s: %s", DB_FILE or "database", summary)
    yield


app = FastAPI(title="Facility Profitability Planner", lifespan=lifespan)

for r in (health, overview, locations, actions, renewals, vendors, demo):
    app.include_router(r.router)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(path: str):
    """Unknown API paths stay a JSON 404 instead of falling through to the frontend."""
    raise HTTPException(status_code=404, detail="Not Found")


# Single-service deploy: serve the built frontend. Registered last so /api/*, /docs and /openapi.json win.
@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    dist = FRONTEND_DIST.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend not built: run `npm run build` in frontend/")
    file = (dist / path).resolve()
    if path and file.is_file() and file.is_relative_to(dist):
        return FileResponse(file)
    # Any other path is a client-side route (e.g. /compare?location=1): let React Router handle it.
    return FileResponse(index)
