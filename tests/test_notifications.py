"""Notification dedup, threshold, and quiet-hours logic (Job Radar Checkpoint 4)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from swetrack.domains.jobs import notifications as notifications_module
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.notifications import QuietHours, notify_new_discoveries
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import sync_source
from swetrack.domains.opportunities.config import load_candidate_profile
from swetrack.domains.opportunities.ranking.tfidf import TfidfRanker


def _sync_strong_new_grad_job(db_session: Session) -> None:
    job = NormalizedJob(
        source_type="greenhouse",
        source_job_id="1",
        company_name="Example Co",
        title="Software Engineer, New Grad 2026",
        description_plain=(
            "New grad software engineer role. Entry level, 0-2 years experience. "
            "Python, AWS, REST APIs, SQL, Docker, FastAPI, Git."
        ),
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",
        source_url="https://boards.greenhouse.io/exampleco/jobs/1",
    )
    sync_source(db_session, source_type="greenhouse", jobs=[job])


def _patch_notification_sender(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent_calls: list[dict] = []
    monkeypatch.setattr(
        notifications_module, "send_macos_notification", lambda **kwargs: sent_calls.append(kwargs) or True
    )
    return sent_calls


def test_notifies_once_for_a_qualifying_job(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_calls = _patch_notification_sender(monkeypatch)
    _sync_strong_new_grad_job(db_session)

    notified = notify_new_discoveries(db_session, ranker=TfidfRanker(), profile=load_candidate_profile(), threshold=0.0)

    assert notified == ["greenhouse:1"]
    assert len(sent_calls) == 1


def test_does_not_renotify_the_same_job(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_calls = _patch_notification_sender(monkeypatch)
    _sync_strong_new_grad_job(db_session)

    notify_new_discoveries(db_session, ranker=TfidfRanker(), profile=load_candidate_profile(), threshold=0.0)
    second = notify_new_discoveries(db_session, ranker=TfidfRanker(), profile=load_candidate_profile(), threshold=0.0)

    assert second == []
    assert len(sent_calls) == 1


def test_below_threshold_job_is_not_notified(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_calls = _patch_notification_sender(monkeypatch)
    _sync_strong_new_grad_job(db_session)

    notified = notify_new_discoveries(db_session, ranker=TfidfRanker(), profile=load_candidate_profile(), threshold=1.01)

    assert notified == []
    assert sent_calls == []


def test_quiet_hours_suppress_notifications(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_calls = _patch_notification_sender(monkeypatch)
    _sync_strong_new_grad_job(db_session)

    quiet = QuietHours(start_hour=0, end_hour=23)  # nearly all-day quiet window
    notified = notify_new_discoveries(
        db_session,
        ranker=TfidfRanker(),
        profile=load_candidate_profile(),
        threshold=0.0,
        quiet_hours=quiet,
        now=datetime(2026, 1, 1, 12, 0),  # inside [0, 23)
    )

    assert notified == []
    assert sent_calls == []


def test_a_job_with_no_tracked_application_is_skipped(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # Defensive: every sync-created job gets an application (Checkpoint 2),
    # but this must not crash if one is ever missing.
    db_session.add(
        DiscoveredJobRecord(
            canonical_key="manual:orphan",
            source_type="manual",
            source_job_id="orphan",
            company_name="Example Co",
            title="Orphaned Job",
        )
    )
    db_session.commit()

    sent_calls = _patch_notification_sender(monkeypatch)
    notified = notify_new_discoveries(db_session, ranker=TfidfRanker(), profile=load_candidate_profile(), threshold=0.0)

    assert notified == []
    assert sent_calls == []


def test_quiet_hours_wraps_past_midnight() -> None:
    quiet = QuietHours(start_hour=22, end_hour=8)
    assert quiet.contains(datetime(2026, 1, 1, 23, 0))
    assert quiet.contains(datetime(2026, 1, 1, 3, 0))
    assert not quiet.contains(datetime(2026, 1, 1, 12, 0))


def test_quiet_hours_non_wrapping_window() -> None:
    quiet = QuietHours(start_hour=1, end_hour=5)
    assert quiet.contains(datetime(2026, 1, 1, 3, 0))
    assert not quiet.contains(datetime(2026, 1, 1, 12, 0))
