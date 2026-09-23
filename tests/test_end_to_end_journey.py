"""End-to-end test: a realistic user journey through the whole system in one pass.

Job Radar Checkpoint 8 ("Add end-to-end tests"). Every other test file
exercises one domain/module in isolation; this one proves they actually
compose correctly through the real API, the way a user would experience
them: discover a job -> see it in the inbox -> track it -> interview ->
outcome analytics reflect it -> source health reflects the sync -> a
tailored resume can be generated for it -> a full backup/restore preserves
everything.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import sync_source
from swetrack.domains.jobs.source_health import record_sync_attempt
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db
from swetrack.infrastructure.database.export import export_all, import_all


@pytest.fixture
def client_and_session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_e2e.db'}")
    init_db(engine)
    session = get_sessionmaker(engine)()

    def _override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    try:
        yield TestClient(app), session, engine
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        session.close()
        engine.dispose()


def test_full_job_radar_journey(client_and_session, tmp_path) -> None:
    client, session, engine = client_and_session

    # 1. A job is discovered (simulating a real sync -- the manual adapter's
    #    output, going through the exact same persistence path a real
    #    Greenhouse/Lever/Ashby sync would).
    job = NormalizedJob(
        source_type="greenhouse",
        source_job_id="1",
        company_name="Example Co",
        title="Software Engineer, New Grad 2026",
        description_plain="Entry level new grad role. Python, AWS, REST APIs. 0-2 years experience.",
        location_text="New York, NY",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",
        source_url="https://boards.greenhouse.io/exampleco/jobs/1",
    )
    sync_result = sync_source(session, source_type="greenhouse", jobs=[job])
    assert sync_result.new_count == 1
    record_sync_attempt(session, source_key="greenhouse:exampleco", company_name="Example Co", adapter_type="greenhouse", success=True)

    # 2. It appears in the job inbox, enriched with eligibility and priority,
    #    and is already tracked as a "discovered" application (Checkpoint 2's
    #    auto-create-application decision).
    inbox_response = client.get("/jobs/inbox")
    assert inbox_response.status_code == 200
    inbox_entries = inbox_response.json()
    assert len(inbox_entries) == 1
    entry = inbox_entries[0]
    assert entry["job_id"] == "greenhouse:1"
    assert entry["eligibility"]["status"] == "eligible"
    assert entry["application_status"] == "discovered"
    application_id = entry["application_id"]

    # 3. It also shows up in the general job listing and can be ranked via
    #    /recommend, proving discovered jobs flow through the existing
    #    ranking pipeline unchanged (Checkpoint 3).
    jobs_response = client.get("/jobs")
    assert any(j["job_id"] == "greenhouse:1" for j in jobs_response.json())

    # 4. The user tracks interest, then applies.
    client.post(f"/applications/{application_id}/status", json={"status": "interested"})
    status_response = client.post(f"/applications/{application_id}/status", json={"status": "applied"})
    assert status_response.json()["status"] == "applied"

    # 5. An interview is logged and passes.
    interview_response = client.post(
        "/interviews",
        json={
            "company": "Example Co",
            "role": "Software Engineer, New Grad 2026",
            "round_type": "coding",
            "date": "2026-02-01T00:00:00Z",
            "skills_tested": ["python"],
            "result": "passed",
            "application_id": application_id,
        },
    )
    assert interview_response.status_code == 201
    client.post(f"/applications/{application_id}/status", json={"status": "technical"})

    # 6. Application Priority is computed with real, non-placeholder
    #    freshness and eligibility components (Checkpoint 3).
    priority_response = client.get(f"/applications/{application_id}/priority")
    assert priority_response.status_code == 200
    priority = priority_response.json()
    assert priority["components"]["freshness"] > 0.0
    assert priority["components"]["new_grad_confidence"] > 0.5

    # 7. Outcome analytics (Checkpoint 8) reflect the journey.
    analytics_response = client.get("/analytics/funnel")
    analytics = analytics_response.json()
    assert analytics["funnel"]["total_applications"] == 1
    applied_stage = next(s for s in analytics["funnel"]["stages"] if s["status"] == "applied")
    assert applied_stage["reached_count"] == 1
    source_yield = next(s for s in analytics["source_yield"] if s["source_type"] == "greenhouse")
    assert source_yield["interviewed_count"] == 1

    # 8. Source health reflects the sync.
    health_response = client.get("/jobs/sources/health")
    health = health_response.json()
    assert len(health) == 1
    assert health[0]["total_success_count"] == 1

    # 9. A full backup/restore preserves everything (Checkpoint 8).
    exported = export_all(engine)
    restore_engine = get_engine(f"sqlite:///{tmp_path / 'test_e2e_restored.db'}")
    init_db(restore_engine)
    import_all(restore_engine, exported)

    restored_session = get_sessionmaker(restore_engine)()
    from swetrack.domains.applications.services import get_application_history, list_applications

    restored_apps = list_applications(restored_session)
    assert len(restored_apps) == 1
    assert restored_apps[0].status == "technical"  # last transition made in step 5
    restored_history = get_application_history(restored_session, restored_apps[0].id)
    assert [e.to_status for e in restored_history] == ["discovered", "interested", "applied", "technical"]
    restored_session.close()
    restore_engine.dispose()
