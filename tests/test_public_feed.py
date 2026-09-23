"""Public discovery feed: generic eligibility filter, merge, retention, and the secret-scan guard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from swetrack.domains.jobs.public_feed import (
    PublicFeedEntry,
    apply_retention,
    contains_forbidden_content,
    generic_candidate,
    merge_feed_entries,
    to_public_feed_entry,
)
from swetrack.domains.jobs.schemas import NormalizedJob

_NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def _job(
    *,
    source_type: str = "greenhouse",
    source_job_id: str = "1",
    title: str = "Software Engineer, New Grad",
    description_plain: str = "Entry level role. 0-2 years experience.",
    company_name: str = "Example Co",
    application_url: str = "https://boards.greenhouse.io/exampleco/jobs/1",
) -> NormalizedJob:
    return NormalizedJob(
        source_type=source_type,
        source_job_id=source_job_id,
        company_name=company_name,
        title=title,
        description_plain=description_plain,
        application_url=application_url,
        source_url=application_url,
    )


def _entry(canonical_key: str, first_seen_at: datetime, **overrides) -> PublicFeedEntry:
    base = {
        "canonical_key": canonical_key,
        "source_type": "greenhouse",
        "source_job_id": canonical_key.split(":")[-1],
        "company_name": "Example Co",
        "title": "Software Engineer, New Grad",
        "application_url": f"https://boards.greenhouse.io/exampleco/jobs/{canonical_key}",
        "first_seen_at": first_seen_at,
        "last_seen_at": first_seen_at,
        "eligibility_status": "eligible",
        "eligibility_confidence": 0.9,
    }
    base.update(overrides)
    return PublicFeedEntry(**base)


# ---------------------------------------------------------------------------
# generic_candidate / to_public_feed_entry
# ---------------------------------------------------------------------------


def test_generic_candidate_has_no_identifying_information() -> None:
    candidate = generic_candidate(year=2026)
    assert candidate.name == "Generic Candidate"
    assert candidate.school == ""
    assert candidate.graduation_year == 2026


def test_eligible_job_produces_an_entry() -> None:
    entry = to_public_feed_entry(_job(), candidate=generic_candidate(year=2026), now=_NOW)
    assert entry is not None
    assert entry.eligibility_status in ("eligible", "uncertain")
    assert entry.canonical_key == "greenhouse:1"


def test_confidently_ineligible_job_is_dropped() -> None:
    senior_job = _job(title="Senior Software Engineer", description_plain="10+ years of experience required.")
    entry = to_public_feed_entry(senior_job, candidate=generic_candidate(year=2026), now=_NOW)
    assert entry is None


# ---------------------------------------------------------------------------
# merge_feed_entries
# ---------------------------------------------------------------------------


def test_merge_adds_a_new_job_with_first_seen_now() -> None:
    fresh = [_entry("greenhouse:1", _NOW)]
    merged = merge_feed_entries([], fresh, now=_NOW)
    assert len(merged) == 1
    assert merged[0].first_seen_at == _NOW
    assert merged[0].last_seen_at == _NOW


def test_merge_preserves_first_seen_and_bumps_last_seen_for_an_existing_job() -> None:
    earlier = _NOW - timedelta(days=3)
    previous = [_entry("greenhouse:1", earlier)]
    fresh = [_entry("greenhouse:1", _NOW, title="Software Engineer, New Grad (Updated)")]

    merged = merge_feed_entries(previous, fresh, now=_NOW)

    assert len(merged) == 1
    assert merged[0].first_seen_at == earlier
    assert merged[0].last_seen_at == _NOW
    assert merged[0].title == "Software Engineer, New Grad (Updated)"


def test_merge_leaves_a_job_missing_from_the_fresh_batch_untouched() -> None:
    earlier = _NOW - timedelta(days=1)
    previous = [_entry("greenhouse:1", earlier)]
    merged = merge_feed_entries(previous, [], now=_NOW)

    assert len(merged) == 1
    assert merged[0].last_seen_at == earlier  # not bumped -- retention handles staleness, not this


# ---------------------------------------------------------------------------
# apply_retention
# ---------------------------------------------------------------------------


def test_retention_drops_entries_older_than_max_age() -> None:
    fresh_entry = _entry("greenhouse:1", _NOW - timedelta(days=1))
    stale_entry = _entry("greenhouse:2", _NOW - timedelta(days=30))

    kept = apply_retention([fresh_entry, stale_entry], now=_NOW, max_age_days=14.0)

    assert [entry.canonical_key for entry in kept] == ["greenhouse:1"]


def test_retention_caps_total_entries_keeping_the_freshest() -> None:
    entries = [_entry(f"greenhouse:{i}", _NOW - timedelta(hours=i)) for i in range(10)]
    kept = apply_retention(entries, now=_NOW, max_entries=3)

    assert len(kept) == 3
    assert kept[0].canonical_key == "greenhouse:0"  # most recently first-seen


def test_retention_drops_cross_source_duplicates_keeping_the_earliest() -> None:
    older = _entry(
        "greenhouse:1", _NOW - timedelta(days=2), application_url="https://boards.greenhouse.io/exampleco/jobs/1"
    )
    newer_duplicate = _entry(
        "lever:abc",
        _NOW - timedelta(days=1),
        source_type="lever",
        application_url="https://boards.greenhouse.io/exampleco/jobs/1",  # same URL -> duplicate
    )

    kept = apply_retention([older, newer_duplicate], now=_NOW)

    assert [entry.canonical_key for entry in kept] == ["greenhouse:1"]


# ---------------------------------------------------------------------------
# contains_forbidden_content (the secret-scan guard)
# ---------------------------------------------------------------------------


def test_contains_forbidden_content_detects_a_marker() -> None:
    assert contains_forbidden_content("path is resume/master_resume.tex") == ["master_resume"]


def test_contains_forbidden_content_is_case_insensitive() -> None:
    assert "master_resume" in contains_forbidden_content("MASTER_RESUME.TEX")


def test_contains_forbidden_content_empty_for_clean_text() -> None:
    assert contains_forbidden_content("Software Engineer, New Grad at Example Co") == []
