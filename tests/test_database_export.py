"""Whole-database export/import round trip (Job Radar Checkpoint 8)."""

from __future__ import annotations

from datetime import datetime, timezone

from swetrack.domains.applications.services import create_application, get_application_history, transition_status
from swetrack.domains.interviews.services import create_interview, list_interviews
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import sync_source
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db
from swetrack.infrastructure.database.export import export_all, import_all


def _fresh_engine():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


def test_export_import_round_trip_preserves_application_history() -> None:
    source_engine = _fresh_engine()
    session = get_sessionmaker(source_engine)()

    application, _ = create_application(session, job_id="JOB-001", status="discovered")
    transition_status(session, application_id=application.id, to_status="interested", notes="Looks promising")
    transition_status(session, application_id=application.id, to_status="applied")

    create_interview(
        session,
        company="Example Co",
        role="Software Engineer",
        round_type="coding",
        date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        skills_tested=["python"],
        result="passed",
        application_id=application.id,
    )

    job = NormalizedJob(
        source_type="greenhouse",
        source_job_id="1",
        company_name="Example Co",
        title="Software Engineer, New Grad",
        application_url="https://example.com/1",
        source_url="https://example.com/1",
    )
    sync_source(session, source_type="greenhouse", jobs=[job])

    exported = export_all(source_engine)
    session.close()

    # Restore onto a completely separate, fresh database.
    target_engine = _fresh_engine()
    inserted = import_all(target_engine, exported)
    assert inserted["applications"] >= 1
    assert inserted["interviews"] == 1

    target_session = get_sessionmaker(target_engine)()

    history = get_application_history(target_session, application.id)
    assert [event.to_status for event in history] == ["discovered", "interested", "applied"]
    assert history[1].notes == "Looks promising"

    interviews = list_interviews(target_session)
    assert len(interviews) == 1
    assert interviews[0].company == "Example Co"
    assert interviews[0].result == "passed"

    discovered = target_session.query(DiscoveredJobRecord).all()
    assert len(discovered) == 1
    assert discovered[0].canonical_key == "greenhouse:1"

    target_session.close()


def test_export_covers_every_registered_table_even_when_empty() -> None:
    engine = _fresh_engine()
    exported = export_all(engine)

    assert exported["schema_version"]
    assert "applications" in exported["tables"]
    assert "discovered_jobs" in exported["tables"]
    assert exported["tables"]["applications"] == []


def test_import_on_top_of_existing_rows_does_not_touch_them() -> None:
    engine = _fresh_engine()
    session = get_sessionmaker(engine)()
    create_application(session, job_id="JOB-001")
    session.close()

    empty_export = {"schema_version": "swetrack-export-v1", "tables": {}}
    inserted = import_all(engine, empty_export)
    assert all(count == 0 for count in inserted.values())

    session = get_sessionmaker(engine)()
    from swetrack.domains.applications.services import list_applications

    assert len(list_applications(session)) == 1
    session.close()
