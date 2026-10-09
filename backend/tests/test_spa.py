"""Single-service deploy: the built frontend, client-side routes, JSON 404s under /api, and seed on startup."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.main
from app import models as m
from app.db import Base, SessionLocal, engine
from app.main import app as fastapi_app
from app.seed import reset_and_seed

INDEX = "<!doctype html><div id=root></div>"


@pytest.fixture
def dist(tmp_path, monkeypatch):
    built = tmp_path / "dist"
    (built / "assets").mkdir(parents=True)
    (built / "index.html").write_text(INDEX)
    (built / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("outside dist")
    monkeypatch.setattr(app.main, "FRONTEND_DIST", built)
    return built


@pytest.mark.parametrize("path", ["/", "/compare?location=1", "/renewals", "/locations/4", "/about"])
def test_client_side_routes_return_index_html(client, seeded, dist, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")


def test_real_files_are_served(client, seeded, dist):
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_paths_cannot_escape_dist(client, seeded, dist):
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        assert "outside dist" not in client.get(path).text


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_unknown_api_paths_are_json_404(client, seeded, dist, method):
    response = client.request(method, "/api/nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_api_routes_still_win_over_the_frontend(client, seeded, dist):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}
    response = client.get("/api/locations/999999")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"


def test_without_a_build_non_api_paths_are_404(client, seeded, tmp_path, monkeypatch):
    monkeypatch.setattr(app.main, "FRONTEND_DIST", tmp_path / "missing")
    response = client.get("/renewals")
    assert response.status_code == 404
    assert "Frontend not built" in response.json()["detail"]


def test_startup_seeds_an_empty_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        with TestClient(fastapi_app):
            with SessionLocal() as db:
                assert db.scalar(select(func.count()).select_from(m.Location)) == 2000
    finally:
        reset_and_seed()
