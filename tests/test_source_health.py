"""Per-source sync health tracking (Job Radar Checkpoint 8)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from swetrack.domains.jobs.source_health import list_source_health, record_sync_attempt


def test_first_success_creates_a_healthy_record(db_session: Session) -> None:
    health = record_sync_attempt(
        db_session, source_key="greenhouse:exampleco", company_name="Example Co", adapter_type="greenhouse", success=True
    )
    assert health.total_success_count == 1
    assert health.total_failure_count == 0
    assert health.consecutive_failures == 0
    assert health.last_error is None
    assert health.last_success_at is not None


def test_first_failure_records_the_error_with_no_success_yet(db_session: Session) -> None:
    health = record_sync_attempt(
        db_session,
        source_key="greenhouse:exampleco",
        company_name="Example Co",
        adapter_type="greenhouse",
        success=False,
        error="404 Not Found",
    )
    assert health.total_failure_count == 1
    assert health.consecutive_failures == 1
    assert health.last_error == "404 Not Found"
    assert health.last_success_at is None


def test_consecutive_failures_accumulate_then_reset_on_success(db_session: Session) -> None:
    kwargs = {"source_key": "greenhouse:exampleco", "company_name": "Example Co", "adapter_type": "greenhouse"}
    record_sync_attempt(db_session, success=False, error="timeout", **kwargs)
    record_sync_attempt(db_session, success=False, error="timeout", **kwargs)
    health = record_sync_attempt(db_session, success=False, error="timeout", **kwargs)
    assert health.consecutive_failures == 3
    assert health.total_failure_count == 3

    recovered = record_sync_attempt(db_session, success=True, **kwargs)
    assert recovered.consecutive_failures == 0
    assert recovered.total_failure_count == 3  # historical count preserved
    assert recovered.total_success_count == 1
    assert recovered.last_error is None


def test_list_source_health_returns_every_tracked_source(db_session: Session) -> None:
    record_sync_attempt(db_session, source_key="greenhouse:a", company_name="A Co", adapter_type="greenhouse", success=True)
    record_sync_attempt(db_session, source_key="lever:b", company_name="B Co", adapter_type="lever", success=False, error="x")

    health = list_source_health(db_session)
    assert {h.source_key for h in health} == {"greenhouse:a", "lever:b"}
