"""Tests for POST /applications, GET /applications, and the status-transition endpoints.

Same isolated-file-DB pattern as test_api_readiness.py: TestClient runs sync
endpoints in a worker thread, so a file-based SQLite DB is used instead of
":memory:" (which would hand each thread its own separate database).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.opportunities.config import DEFAULT_JOBS_PATH, load_jobs
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db

KNOWN_JOB_ID = load_jobs(DEFAULT_JOBS_PATH)[0].job_id


@pytest.fixture
def client(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_applications.db'}")
    init_db(engine)
    session = get_sessionmaker(engine)()

    def _override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        session.close()
        engine.dispose()


def test_post_application_creates_with_default_status(client):
    response = client.post("/applications", json={"job_id": KNOWN_JOB_ID})

    assert response.status_code == 201
    body = response.json()
    assert body["job_id"] == KNOWN_JOB_ID
    assert body["status"] == "discovered"


def test_post_application_rejects_unknown_job_id(client):
    response = client.post("/applications", json={"job_id": "NOT-A-REAL-JOB"})
    assert response.status_code == 422


def test_get_application_by_id_returns_created_application(client):
    created = client.post("/applications", json={"job_id": KNOWN_JOB_ID}).json()

    response = client.get(f"/applications/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_application_by_id_404s_for_unknown_application(client):
    response = client.get("/applications/does-not-exist")
    assert response.status_code == 404


def test_post_application_status_transitions_and_is_reflected_in_get(client):
    created = client.post("/applications", json={"job_id": KNOWN_JOB_ID}).json()

    response = client.post(f"/applications/{created['id']}/status", json={"status": "applied"})
    assert response.status_code == 200
    assert response.json()["status"] == "applied"

    refreshed = client.get(f"/applications/{created['id']}").json()
    assert refreshed["status"] == "applied"


def test_post_application_status_404s_for_unknown_application(client):
    response = client.post("/applications/does-not-exist/status", json={"status": "applied"})
    assert response.status_code == 404


def test_get_application_history_lists_transitions_in_order(client):
    created = client.post("/applications", json={"job_id": KNOWN_JOB_ID}).json()
    client.post(f"/applications/{created['id']}/status", json={"status": "applied"})
    client.post(f"/applications/{created['id']}/status", json={"status": "oa"})

    response = client.get(f"/applications/{created['id']}/history")

    assert response.status_code == 200
    statuses = [event["to_status"] for event in response.json()]
    assert statuses == ["discovered", "applied", "oa"]


def test_get_applications_filters_by_status(client):
    client.post("/applications", json={"job_id": KNOWN_JOB_ID, "status": "applied"})
    client.post("/applications", json={"job_id": KNOWN_JOB_ID, "status": "discovered"})

    response = client.get("/applications", params={"status": "applied"})

    assert response.status_code == 200
    assert all(app["status"] == "applied" for app in response.json())
