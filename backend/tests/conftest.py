import os

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory; must be set before app.db is imported

import pytest
from fastapi.testclient import TestClient

from app import loaders, services
from app.db import SessionLocal
from app.main import app
from app.seed import reset_and_seed


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def seeded():
    """Seed the in-memory database once. Tests must not change it; use `mutable_db` for that."""
    reset_and_seed()
    with SessionLocal() as db:
        yield db


@pytest.fixture
def mutable_db():
    """A freshly seeded session for tests that edit records; reseeds afterwards."""
    reset_and_seed()
    with SessionLocal() as db:
        yield db
    reset_and_seed()


@pytest.fixture
def ctx(seeded):
    return services.load_context(seeded)


@pytest.fixture
def records(seeded):
    """records("PHX-01") -> LocationRecords loaded from the seeded database."""
    return lambda code, db=seeded: loaders.load_records(db, loaders.location_by_code(db, code).id)
