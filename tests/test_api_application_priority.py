"""Tests for GET /applications/{id}/priority and GET /applications/priority."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.opportunities.config import DEFAULT_JOBS_PATH, load_jobs
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db

KNOWN_JOB_ID = load_jobs(DEFAULT_JOBS_PATH)[0].job_id


@pytest.fixture
def client(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_application_priority.db'}")
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


def test_application_priority_endpoint_returns_score_and_components(client):
    created = client.post("/applications", json={"job_id": KNOWN_JOB_ID}).json()

    response = client.get(f"/applications/{created['id']}/priority")

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == created["id"]
    assert body["job_id"] == KNOWN_JOB_ID
    assert 0.0 <= body["score"] <= 1.0
    assert set(body["components"].keys()) == {
        "role_fit",
        "readiness",
        "freshness",
        "new_grad_confidence",
        "user_preference",
        "company_interest",
        "compensation_fit",
        "deadline_urgency",
    }
    assert "readiness_score" in body["readiness"]


def test_application_priority_endpoint_404s_for_unknown_application(client):
    response = client.get("/applications/does-not-exist/priority")
    assert response.status_code == 404


def test_application_priority_endpoint_rejects_unknown_ranker(client):
    created = client.post("/applications", json={"job_id": KNOWN_JOB_ID}).json()

    response = client.get(f"/applications/{created['id']}/priority", params={"ranker": "not-a-real-ranker"})

    assert response.status_code == 422


def test_applications_priority_endpoint_ranks_tracked_applications(client):
    other_job_id = load_jobs(DEFAULT_JOBS_PATH)[1].job_id
    client.post("/applications", json={"job_id": KNOWN_JOB_ID})
    client.post("/applications", json={"job_id": other_job_id})

    response = client.get("/applications/priority")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    # Sorted highest score first (not the registration/no-route-conflict-with-{id} check
    # alone -- a 404 or a single-object body would mean "priority" was swallowed by
    # GET /applications/{application_id} instead of this route).
    scores = [item["score"] for item in body]
    assert scores == sorted(scores, reverse=True)


def test_applications_priority_endpoint_respects_top_k(client):
    other_job_id = load_jobs(DEFAULT_JOBS_PATH)[1].job_id
    client.post("/applications", json={"job_id": KNOWN_JOB_ID})
    client.post("/applications", json={"job_id": other_job_id})

    response = client.get("/applications/priority", params={"top_k": 1})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_applications_priority_endpoint_filters_by_status(client):
    client.post("/applications", json={"job_id": KNOWN_JOB_ID, "status": "applied"})
    client.post("/applications", json={"job_id": KNOWN_JOB_ID, "status": "discovered"})

    response = client.get("/applications/priority", params={"status": "applied"})

    assert response.status_code == 200
    assert all(item["status"] == "applied" for item in response.json())
