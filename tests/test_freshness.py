"""Freshness decay scoring (Job Radar Checkpoint 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from swetrack.domains.jobs.freshness import compute_freshness

_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _score(hours_ago: float) -> float:
    return compute_freshness(
        source_published_at=_NOW - timedelta(hours=hours_ago),
        first_seen_at=None,
        now=_NOW,
    )


def test_no_timestamps_scores_zero() -> None:
    assert compute_freshness(source_published_at=None, first_seen_at=None, now=_NOW) == 0.0


def test_falls_back_to_first_seen_at_when_published_at_missing() -> None:
    result = compute_freshness(source_published_at=None, first_seen_at=_NOW - timedelta(hours=1), now=_NOW)
    assert result == 1.0


def test_published_at_preferred_over_first_seen_at() -> None:
    # Published 5 days ago (0.25 bucket) but only just discovered (1.0 bucket)
    # -- published_at wins per Section 8 ("source_updated_at must not be
    # presented as a publish date" implies published_at is the trustworthy
    # signal when present).
    result = compute_freshness(
        source_published_at=_NOW - timedelta(days=5),
        first_seen_at=_NOW - timedelta(minutes=1),
        now=_NOW,
    )
    assert result == 0.25


def test_decay_buckets_match_the_handoff_table() -> None:
    assert _score(1) == 1.0
    assert _score(4) == 0.9
    assert _score(9) == 0.8
    assert _score(20) == 0.65
    assert _score(48) == 0.45
    assert _score(150) == 0.25
    assert _score(24 * 30) == 0.10


def test_freshness_is_monotonically_non_increasing_with_age() -> None:
    ages = [0.5, 3, 8, 18, 36, 96, 150, 300]
    scores = [_score(age) for age in ages]
    assert scores == sorted(scores, reverse=True)


def test_future_or_zero_age_does_not_error() -> None:
    # A clock-skew edge case (source_published_at slightly after `now`)
    # should not raise or go negative.
    result = compute_freshness(source_published_at=_NOW + timedelta(minutes=5), first_seen_at=None, now=_NOW)
    assert result == 1.0
