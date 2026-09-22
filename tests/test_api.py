"""Tests for GET /health, GET /jobs, and POST /recommend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.opportunities.config import DEFAULT_JOBS_PATH, load_jobs
from swetrack.domains.opportunities.ranking import embeddings
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db


@pytest.fixture
def client(tmp_path):
    """Isolated file-DB TestClient.

    A file (not ":memory:") is required because TestClient runs endpoints
    in a worker thread -- see test_api_applications.py's docstring for the
    same pattern. Job Radar Checkpoint 3: GET /jobs and POST /recommend now
    also read discovered_jobs via the shared DB session, so they need the
    same isolation as every other DB-touching endpoint test, rather than
    accidentally depending on whatever is in the real local var/swetrack.db.
    """
    engine = get_engine(f"sqlite:///{tmp_path / 'test_api.db'}")
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


def test_dashboard_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SWETrack" in response.text


def test_health_returns_ok_and_does_not_load_embedding_model(client):
    embeddings._model_cache.clear()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert embeddings._model_cache == {}


def test_get_jobs_returns_all_sample_jobs_matching_schema(client):
    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    expected_count = len(load_jobs(DEFAULT_JOBS_PATH))
    assert len(jobs) == expected_count
    assert all("job_id" in job and "title" in job for job in jobs)


def test_get_jobs_respects_limit_and_offset(client):
    response = client.get("/jobs", params={"limit": 3, "offset": 2})
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 3

    all_jobs = client.get("/jobs").json()
    assert jobs == all_jobs[2:5]


def test_recommend_with_example_profile_and_tfidf(client):
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "tfidf", "top_k": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ranker"] == "tfidf"
    assert body["top_k"] == 5
    assert len(body["results"]) == 5

    scores = [item["score"] for item in body["results"]]
    assert scores == sorted(scores, reverse=True)
    ranks = [item["rank"] for item in body["results"]]
    assert ranks == [1, 2, 3, 4, 5]


def test_recommend_with_supplied_profile(client):
    response = client.post(
        "/recommend",
        json={
            "profile": {
                "skills": ["Python", "AWS", "FastAPI"],
                "experience": "Backend engineer building REST APIs in Python.",
                "preferred_roles": ["Backend Engineer"],
            },
            "ranker": "tfidf",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 3


def test_recommend_requires_profile_or_explicit_example_flag(client):
    response = client.post("/recommend", json={"ranker": "tfidf", "top_k": 3})
    assert response.status_code == 422


def test_recommend_rejects_invalid_ranker(client):
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "not-a-real-ranker", "top_k": 3},
    )
    assert response.status_code == 422


def test_recommend_rejects_non_positive_top_k(client):
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "tfidf", "top_k": 0},
    )
    assert response.status_code == 422


def test_recommend_rejects_top_k_exceeding_available_jobs(client):
    total_jobs = len(load_jobs(DEFAULT_JOBS_PATH))
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "tfidf", "top_k": total_jobs + 1},
    )
    assert response.status_code == 422


def test_recommend_rejects_malformed_profile_missing_skills(client):
    response = client.post(
        "/recommend",
        json={
            "profile": {"skills": [], "experience": "Backend engineer."},
            "ranker": "tfidf",
            "top_k": 3,
        },
    )
    assert response.status_code == 422
