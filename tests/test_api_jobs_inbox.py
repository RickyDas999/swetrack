"""Tests for GET /jobs/inbox (Job Radar Checkpoint 4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import sync_source
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db


@pytest.fixture
def client_and_session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_jobs_inbox.db'}")
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


def _new_grad_job(source_job_id: str = "1") -> NormalizedJob:
    return NormalizedJob(
        source_type="greenhouse",
        source_job_id=source_job_id,
        company_name="Example Co",
        title="Software Engineer, New Grad 2026",
        description_plain="Entry level new grad role. 0-2 years experience. Python and AWS.",
        location_text="New York, NY",
        application_url=f"https://boards.greenhouse.io/exampleco/jobs/{source_job_id}",
        source_url=f"https://boards.greenhouse.io/exampleco/jobs/{source_job_id}",
    )


def test_inbox_is_empty_with_no_discovered_jobs(client_and_session):
    client, _ = client_and_session
    response = client.get("/jobs/inbox")
    assert response.status_code == 200
    assert response.json() == []


def test_inbox_entry_distinguishes_published_from_first_found(client_and_session):
    client, session = client_and_session
    sync_source(session, source_type="greenhouse", jobs=[_new_grad_job()])

    response = client.get("/jobs/inbox")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1

    entry = entries[0]
    assert "source_published_at" in entry
    assert "first_seen_at" in entry
    assert entry["source_published_at"] is None  # this fixture never set a published date
    assert entry["first_seen_at"] is not None
    assert entry["application_status"] == "discovered"
    assert entry["eligibility"]["status"] == "eligible"
    assert entry["priority"] is not None


def test_inbox_filters_by_eligibility_status(client_and_session):
    client, session = client_and_session
    sync_source(session, source_type="greenhouse", jobs=[_new_grad_job()])

    matching = client.get("/jobs/inbox", params={"eligibility_status": "eligible"})
    assert len(matching.json()) == 1

    non_matching = client.get("/jobs/inbox", params={"eligibility_status": "ineligible"})
    assert non_matching.json() == []


def test_inbox_filters_by_application_status(client_and_session):
    client, session = client_and_session
    sync_source(session, source_type="greenhouse", jobs=[_new_grad_job()])

    matching = client.get("/jobs/inbox", params={"application_status": "discovered"})
    assert len(matching.json()) == 1

    non_matching = client.get("/jobs/inbox", params={"application_status": "applied"})
    assert non_matching.json() == []


def test_inbox_filters_by_min_priority(client_and_session):
    client, session = client_and_session
    sync_source(session, source_type="greenhouse", jobs=[_new_grad_job()])

    too_high = client.get("/jobs/inbox", params={"min_priority": 0.99})
    assert too_high.json() == []

    lenient = client.get("/jobs/inbox", params={"min_priority": 0.0})
    assert len(lenient.json()) == 1


def test_inbox_excludes_cross_source_duplicates(client_and_session):
    client, session = client_and_session
    greenhouse_job = _new_grad_job(source_job_id="1")
    lever_job = NormalizedJob(
        source_type="lever",
        source_job_id="dup",
        company_name="Example Co",
        title="Software Engineer, New Grad 2026",
        description_plain="Entry level new grad role. 0-2 years experience. Python and AWS.",
        location_text="New York, NY",
        application_url=greenhouse_job.application_url,
        source_url=greenhouse_job.application_url,
    )
    sync_source(session, source_type="greenhouse", jobs=[greenhouse_job])
    sync_source(session, source_type="lever", jobs=[lever_job])

    response = client.get("/jobs/inbox")
    assert len(response.json()) == 1
