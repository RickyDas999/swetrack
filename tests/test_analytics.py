"""Outcome analytics: funnel, time-to-apply, source yield, response rate (Checkpoint 8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from swetrack.domains.applications.analytics import (
    compute_analytics_report,
    compute_funnel,
    compute_response_rate,
    compute_source_yield,
    compute_time_to_apply,
)
from swetrack.domains.applications.models import ApplicationRecord, ApplicationStatusEventRecord
from swetrack.domains.applications.services import create_application, transition_status
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import sync_source

_NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def _discovered_job(db_session: Session, *, source_type: str = "greenhouse", source_job_id: str = "1") -> str:
    """Sync one discovered job (auto-creates a 'discovered' application) and return its job_id."""
    job = NormalizedJob(
        source_type=source_type,
        source_job_id=source_job_id,
        company_name="Example Co",
        title="Software Engineer, New Grad",
        application_url=f"https://example.com/{source_job_id}",
        source_url=f"https://example.com/{source_job_id}",
    )
    sync_source(db_session, source_type=source_type, jobs=[job])
    return f"{source_type}:{source_job_id}"


def _application_with_controlled_timestamps(
    db_session: Session, *, job_id: str, created_at: datetime, applied_at: datetime | None
) -> str:
    """Direct model construction, bypassing services.py's default-now timestamps, for deterministic time math."""
    app = ApplicationRecord(job_id=job_id, status="discovered", created_at=created_at, updated_at=created_at)
    db_session.add(app)
    db_session.flush()
    db_session.add(
        ApplicationStatusEventRecord(application_id=app.id, from_status=None, to_status="discovered", timestamp=created_at)
    )
    if applied_at is not None:
        app.status = "applied"
        db_session.add(
            ApplicationStatusEventRecord(
                application_id=app.id, from_status="discovered", to_status="applied", timestamp=applied_at
            )
        )
    db_session.commit()
    return app.id


# ---------------------------------------------------------------------------
# compute_funnel
# ---------------------------------------------------------------------------


def test_funnel_counts_ever_reached_not_current_status(db_session: Session) -> None:
    application, _ = create_application(db_session, job_id="JOB-001", status="interested")
    transition_status(db_session, application_id=application.id, to_status="applied")
    transition_status(db_session, application_id=application.id, to_status="rejected")

    funnel = compute_funnel(db_session)

    by_status = {stage.status: stage.reached_count for stage in funnel.stages}
    assert by_status["applied"] == 1  # still counted, even though current status is "rejected"
    assert funnel.rejected_count == 1
    assert funnel.total_applications == 1


def test_funnel_is_empty_with_no_applications(db_session: Session) -> None:
    funnel = compute_funnel(db_session)
    assert funnel.total_applications == 0
    assert all(stage.reached_count == 0 for stage in funnel.stages)
    assert funnel.rejected_count == 0


# ---------------------------------------------------------------------------
# compute_time_to_apply
# ---------------------------------------------------------------------------


def test_time_to_apply_computes_hours_between_creation_and_first_applied(db_session: Session) -> None:
    job_id = _discovered_job(db_session, source_job_id="a")
    _application_with_controlled_timestamps(
        db_session, job_id=job_id, created_at=_NOW, applied_at=_NOW + timedelta(hours=48)
    )

    stats = compute_time_to_apply(db_session)

    assert stats.sample_size == 1
    assert stats.median_hours == 48.0
    assert stats.mean_hours == 48.0


def test_time_to_apply_excludes_applications_never_applied(db_session: Session) -> None:
    job_id = _discovered_job(db_session, source_job_id="b")
    _application_with_controlled_timestamps(db_session, job_id=job_id, created_at=_NOW, applied_at=None)

    stats = compute_time_to_apply(db_session)

    assert stats.sample_size == 0
    assert stats.median_hours is None


# ---------------------------------------------------------------------------
# compute_source_yield
# ---------------------------------------------------------------------------


def test_source_yield_categorizes_discovered_jobs_by_source_type(db_session: Session) -> None:
    _discovered_job(db_session, source_type="greenhouse", source_job_id="1")
    _discovered_job(db_session, source_type="lever", source_job_id="2")

    report = compute_source_yield(db_session)
    by_source = {entry.source_type: entry for entry in report}

    assert by_source["greenhouse"].discovered_count == 1
    assert by_source["greenhouse"].applications_count == 1  # auto-created "discovered" application
    assert by_source["lever"].discovered_count == 1


def test_source_yield_categorizes_csv_sample_jobs_as_sample(db_session: Session) -> None:
    application, _ = create_application(db_session, job_id="JOB-001")  # a real sample CSV job id
    report = compute_source_yield(db_session)
    sample_entry = next(entry for entry in report if entry.source_type == "sample")
    assert sample_entry.applications_count == 1


def test_source_yield_counts_interviewed_and_offer_from_history(db_session: Session) -> None:
    job_id = _discovered_job(db_session, source_job_id="c")
    application, _ = create_application(db_session, job_id=job_id, status="interested")
    transition_status(db_session, application_id=application.id, to_status="applied")
    transition_status(db_session, application_id=application.id, to_status="technical")
    transition_status(db_session, application_id=application.id, to_status="offer")

    report = compute_source_yield(db_session)
    entry = next(e for e in report if e.source_type == "greenhouse")
    assert entry.interviewed_count == 1
    assert entry.offer_count == 1


# ---------------------------------------------------------------------------
# compute_response_rate
# ---------------------------------------------------------------------------


def test_response_rate_is_none_with_zero_applied(db_session: Session) -> None:
    stats = compute_response_rate(db_session)
    assert stats.applied_count == 0
    assert stats.response_rate is None


def test_response_rate_computed_correctly(db_session: Session) -> None:
    job_id_1 = _discovered_job(db_session, source_job_id="d1")
    app1, _ = create_application(db_session, job_id=job_id_1)
    transition_status(db_session, application_id=app1.id, to_status="applied")
    transition_status(db_session, application_id=app1.id, to_status="technical")

    job_id_2 = _discovered_job(db_session, source_job_id="d2")
    app2, _ = create_application(db_session, job_id=job_id_2)
    transition_status(db_session, application_id=app2.id, to_status="applied")
    # app2 never gets a response

    stats = compute_response_rate(db_session)
    assert stats.applied_count == 2
    assert stats.responded_count == 1
    assert stats.response_rate == 0.5


# ---------------------------------------------------------------------------
# compute_analytics_report
# ---------------------------------------------------------------------------


def test_analytics_report_bundles_every_metric(db_session: Session) -> None:
    report = compute_analytics_report(db_session, now=_NOW)
    assert report.generated_at == _NOW
    assert report.funnel.total_applications == 0
    assert report.time_to_apply.sample_size == 0
    assert report.source_yield == []
    assert report.response_rate.response_rate is None
    assert "not causal" in report.caveat
