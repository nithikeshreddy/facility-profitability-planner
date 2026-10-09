from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  (registers tables for create_all)
from app.db import Base, engine
from app.routers import actions, demo, health, locations, overview, renewals, vendors

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Facility Profitability Planner", lifespan=lifespan)

for r in (health, overview, locations, actions, renewals, vendors, demo):
    app.include_router(r.router)

# Single-service deploy: serve the built frontend when it exists. Mounted last so /api/* wins.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
