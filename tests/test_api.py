"""Tests for GET /health, GET /jobs, and POST /recommend."""

from __future__ import annotations

from fastapi.testclient import TestClient

from swetrack.api import app
from swetrack.domains.opportunities.config import DEFAULT_JOBS_PATH, load_jobs
from swetrack.domains.opportunities.ranking import embeddings

client = TestClient(app)


def test_dashboard_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SWETrack" in response.text


def test_health_returns_ok_and_does_not_load_embedding_model():
    embeddings._model_cache.clear()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert embeddings._model_cache == {}


def test_get_jobs_returns_all_sample_jobs_matching_schema():
    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    expected_count = len(load_jobs(DEFAULT_JOBS_PATH))
    assert len(jobs) == expected_count
    assert all("job_id" in job and "title" in job for job in jobs)


def test_get_jobs_respects_limit_and_offset():
    response = client.get("/jobs", params={"limit": 3, "offset": 2})
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 3

    all_jobs = client.get("/jobs").json()
    assert jobs == all_jobs[2:5]


def test_recommend_with_example_profile_and_tfidf():
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


def test_recommend_with_supplied_profile():
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


def test_recommend_requires_profile_or_explicit_example_flag():
    response = client.post("/recommend", json={"ranker": "tfidf", "top_k": 3})
    assert response.status_code == 422


def test_recommend_rejects_invalid_ranker():
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "not-a-real-ranker", "top_k": 3},
    )
    assert response.status_code == 422


def test_recommend_rejects_non_positive_top_k():
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "tfidf", "top_k": 0},
    )
    assert response.status_code == 422


def test_recommend_rejects_top_k_exceeding_available_jobs():
    total_jobs = len(load_jobs(DEFAULT_JOBS_PATH))
    response = client.post(
        "/recommend",
        json={"use_example_profile": True, "ranker": "tfidf", "top_k": total_jobs + 1},
    )
    assert response.status_code == 422


def test_recommend_rejects_malformed_profile_missing_skills():
    response = client.post(
        "/recommend",
        json={
            "profile": {"skills": [], "experience": "Backend engineer."},
            "ranker": "tfidf",
            "top_k": 3,
        },
    )
    assert response.status_code == 422
