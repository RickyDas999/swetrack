"""Tests for POST /interviews, GET /interviews, and GET /interviews/{id}.

Same isolated-file-DB pattern as test_api_applications.py: TestClient runs
sync endpoints in a worker thread, so a file-based SQLite DB is used instead
of ":memory:" (which would hand each thread its own separate database).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db

INTERVIEW_PAYLOAD = {
    "company": "Figma",
    "role": "SWE",
    "round_type": "coding",
    "date": "2026-01-15T00:00:00Z",
    "skills_tested": ["graphs"],
}


@pytest.fixture
def client(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_interviews.db'}")
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


def test_post_interview_creates_with_default_pending_result(client):
    response = client.post("/interviews", json=INTERVIEW_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["company"] == "Figma"
    assert body["result"] == "pending"


def test_post_interview_rejects_unknown_skill_id(client):
    response = client.post("/interviews", json={**INTERVIEW_PAYLOAD, "skills_tested": ["not-a-real-skill"]})
    assert response.status_code == 422


def test_get_interview_by_id_returns_created_interview(client):
    created = client.post("/interviews", json=INTERVIEW_PAYLOAD).json()

    response = client.get(f"/interviews/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_interview_by_id_404s_for_unknown_interview(client):
    response = client.get("/interviews/does-not-exist")
    assert response.status_code == 404


def test_get_interviews_filters_by_round_type(client):
    client.post("/interviews", json={**INTERVIEW_PAYLOAD, "round_type": "coding"})
    client.post("/interviews", json={**INTERVIEW_PAYLOAD, "round_type": "behavioral"})

    response = client.get("/interviews", params={"round_type": "behavioral"})

    assert response.status_code == 200
    assert all(interview["round_type"] == "behavioral" for interview in response.json())
