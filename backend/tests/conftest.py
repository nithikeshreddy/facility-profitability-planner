import os

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory; must be set before app.db is imported

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
