"""Job Radar Checkpoint 2: discovered-job persistence, dedup, and revision handling."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from swetrack.domains.applications.services import create_application, list_applications
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import list_discovered_job_records, sync_source


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime read back through SQLite for a safe comparison.

    SQLite has no native timezone-aware storage: a DateTime(timezone=True)
    column round-trips as naive once the original in-memory ORM object is
    garbage collected and a fresh query re-loads the row (a SQLAlchemy+SQLite
    limitation, not specific to this table). Every timestamp this project
    writes is UTC, so a naive value read back is treated as already-UTC
    rather than compared directly against a tz-aware one.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _job(
    *,
    source_type: str = "greenhouse",
    source_job_id: str = "1",
    company_name: str = "Example Co",
    title: str = "Software Engineer, New Grad",
    location_text: str = "New York, NY",
    description_plain: str = "Join our new grad engineering team building backend services.",
    application_url: str = "https://boards.greenhouse.io/exampleco/jobs/1",
) -> NormalizedJob:
    return NormalizedJob(
        source_type=source_type,
        source_job_id=source_job_id,
        company_name=company_name,
        title=title,
        location_text=location_text,
        description_plain=description_plain,
        application_url=application_url,
        source_url=application_url,
    )


def test_syncing_the_same_job_twice_creates_no_duplicate_row(db_session: Session) -> None:
    sync_source(db_session, source_type="greenhouse", jobs=[_job()])
    sync_source(db_session, source_type="greenhouse", jobs=[_job()])

    assert db_session.query(DiscoveredJobRecord).count() == 1


def test_sync_auto_creates_a_discovered_application(db_session: Session) -> None:
    result = sync_source(db_session, source_type="greenhouse", jobs=[_job()])
    assert result.new_count == 1

    applications = list_applications(db_session)
    assert len(applications) == 1
    assert applications[0].status == "discovered"
    assert applications[0].job_id == "greenhouse:1"


def test_second_sync_does_not_create_a_second_application(db_session: Session) -> None:
    sync_source(db_session, source_type="greenhouse", jobs=[_job()])
    result = sync_source(db_session, source_type="greenhouse", jobs=[_job()])

    assert result.new_count == 0
    assert result.unchanged_count == 1
    assert len(list_applications(db_session)) == 1


def test_updated_description_preserves_first_seen_at_and_bumps_last_seen_at(db_session: Session) -> None:
    sync_source(db_session, source_type="greenhouse", jobs=[_job(description_plain="Original description.")])
    row_after_first = db_session.query(DiscoveredJobRecord).one()
    first_seen_at = row_after_first.first_seen_at
    last_seen_at_after_first = row_after_first.last_seen_at

    result = sync_source(db_session, source_type="greenhouse", jobs=[_job(description_plain="Updated description.")])
    assert result.updated_count == 1

    row_after_second = db_session.query(DiscoveredJobRecord).one()
    assert _as_utc(row_after_second.first_seen_at) == _as_utc(first_seen_at)
    assert _as_utc(row_after_second.last_seen_at) >= _as_utc(last_seen_at_after_first)
    assert row_after_second.description_plain == "Updated description."


def test_unchanged_resync_still_bumps_last_seen_at(db_session: Session) -> None:
    sync_source(db_session, source_type="greenhouse", jobs=[_job()])
    first_last_seen = db_session.query(DiscoveredJobRecord).one().last_seen_at

    result = sync_source(db_session, source_type="greenhouse", jobs=[_job()])
    assert result.unchanged_count == 1

    row_after_second = db_session.query(DiscoveredJobRecord).one()
    assert _as_utc(row_after_second.last_seen_at) >= _as_utc(first_last_seen)


def test_cross_source_duplicate_is_flagged_not_duplicated(db_session: Session) -> None:
    greenhouse_job = _job(
        source_type="greenhouse",
        source_job_id="1",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1?utm_source=linkedin",
    )
    lever_job = _job(
        source_type="lever",
        source_job_id="abc",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",
    )

    sync_source(db_session, source_type="greenhouse", jobs=[greenhouse_job])
    result = sync_source(db_session, source_type="lever", jobs=[lever_job])

    assert result.duplicate_count == 1
    rows = db_session.query(DiscoveredJobRecord).all()
    assert len(rows) == 2

    lever_row = next(row for row in rows if row.source_type == "lever")
    greenhouse_row = next(row for row in rows if row.source_type == "greenhouse")
    assert lever_row.duplicate_of_id == greenhouse_row.id

    # Only the primary (non-duplicate) row gets an auto-created application.
    assert len(list_applications(db_session)) == 1


def test_duplicate_detected_via_matching_description_when_urls_differ(db_session: Session) -> None:
    shared_description = "We are hiring a backend engineer to build our core platform in Python and AWS."
    job_a = _job(
        source_type="greenhouse",
        source_job_id="1",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",
        description_plain=shared_description,
    )
    job_b = _job(
        source_type="ashby",
        source_job_id="2",
        application_url="https://jobs.ashbyhq.com/exampleco/2",
        description_plain=shared_description,
    )

    sync_source(db_session, source_type="greenhouse", jobs=[job_a])
    result = sync_source(db_session, source_type="ashby", jobs=[job_b])

    assert result.duplicate_count == 1


def test_different_company_same_title_is_not_flagged_as_duplicate(db_session: Session) -> None:
    job_a = _job(source_type="greenhouse", source_job_id="1", company_name="Example Co")
    job_b = _job(source_type="lever", source_job_id="2", company_name="Different Co")

    sync_source(db_session, source_type="greenhouse", jobs=[job_a])
    result = sync_source(db_session, source_type="lever", jobs=[job_b])

    assert result.duplicate_count == 0
    assert len(list_applications(db_session)) == 2


def test_discovered_job_can_be_tracked_like_any_other_application(db_session: Session) -> None:
    sync_source(db_session, source_type="greenhouse", jobs=[_job()])

    # Simulates a user manually re-tracking a discovered job at a different
    # status -- proves applications.services._job_exists now recognizes
    # DB-backed discovered jobs, not just the sample CSV.
    application, _ = create_application(db_session, job_id="greenhouse:1", status="interested")
    assert application.job_id == "greenhouse:1"


def test_list_discovered_job_records_converts_to_job_record_shape(db_session: Session) -> None:
    sync_source(db_session, source_type="greenhouse", jobs=[_job()])

    records = list_discovered_job_records(db_session)

    assert len(records) == 1
    record = records[0]
    assert record.job_id == "greenhouse:1"
    assert record.company == "Example Co"
    assert record.title == "Software Engineer, New Grad"
    assert record.source == "discovered"


def test_list_discovered_job_records_excludes_duplicates_by_default(db_session: Session) -> None:
    greenhouse_job = _job(
        source_type="greenhouse",
        source_job_id="1",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",
    )
    lever_job = _job(
        source_type="lever",
        source_job_id="abc",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",
    )
    sync_source(db_session, source_type="greenhouse", jobs=[greenhouse_job])
    sync_source(db_session, source_type="lever", jobs=[lever_job])

    visible = list_discovered_job_records(db_session)
    assert len(visible) == 1

    everything = list_discovered_job_records(db_session, include_duplicates=True)
    assert len(everything) == 2
