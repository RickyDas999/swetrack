"""Tests for GET /analytics/funnel and GET /jobs/sources/health (Checkpoint 8)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.jobs.source_health import record_sync_attempt
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db


@pytest.fixture
def client_and_session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_analytics.db'}")
    init_db(engine)
    session = get_sessionmaker(engine)()

    def _override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    try:
        yield TestClient(app), session
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        session.close()
        engine.dispose()


def test_analytics_funnel_returns_empty_report_with_no_data(client_and_session):
    client, _ = client_and_session
    response = client.get("/analytics/funnel")
    assert response.status_code == 200
    body = response.json()
    assert body["funnel"]["total_applications"] == 0
    assert body["response_rate"]["response_rate"] is None
    assert "not causal" in body["caveat"]


def test_analytics_funnel_reflects_a_tracked_application(client_and_session):
    client, _ = client_and_session
    created = client.post("/applications", json={"job_id": "JOB-001", "status": "applied"}).json()
    assert created["status"] == "applied"

    response = client.get("/analytics/funnel")
    body = response.json()
    assert body["funnel"]["total_applications"] == 1
    applied_stage = next(s for s in body["funnel"]["stages"] if s["status"] == "applied")
    assert applied_stage["reached_count"] == 1


def test_job_sources_health_is_empty_before_any_sync(client_and_session):
    client, _ = client_and_session
    response = client.get("/jobs/sources/health")
    assert response.status_code == 200
    assert response.json() == []


def test_job_sources_health_reflects_recorded_attempts(client_and_session):
    client, session = client_and_session
    record_sync_attempt(
        session, source_key="greenhouse:exampleco", company_name="Example Co", adapter_type="greenhouse", success=True
    )

    response = client.get("/jobs/sources/health")
    body = response.json()
    assert len(body) == 1
    assert body[0]["source_key"] == "greenhouse:exampleco"
    assert body[0]["total_success_count"] == 1
