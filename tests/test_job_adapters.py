"""Greenhouse adapter payload -> NormalizedJob mapping (Job Radar Checkpoint 1).

Uses httpx.MockTransport so GreenhouseAdapter.fetch() exercises its real HTTP
call path end-to-end with zero live network access, per
SWETrack_Job_Radar_Claude_Code_Handoff.md Section 17: "Mock HTTP using
recorded/redacted fixtures; CI must not depend on live ATS availability."
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from swetrack.domains.jobs.adapters.base import strip_html_to_text
from swetrack.domains.jobs.adapters.greenhouse import GreenhouseAdapter, _parse_timestamp
from swetrack.domains.jobs.schemas import NormalizedJob

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ats" / "greenhouse_sample.json"
_FIXTURE_PAYLOAD = json.loads(_FIXTURE_PATH.read_text())


def _mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/boards/exampleco/jobs"
        assert request.url.params["content"] == "true"
        return httpx.Response(200, json=_FIXTURE_PAYLOAD)

    return httpx.MockTransport(handler)


def _fetch_fixture_jobs() -> list[NormalizedJob]:
    client = httpx.Client(transport=_mock_transport())
    adapter = GreenhouseAdapter("exampleco", "Example Co", client=client)
    return adapter.fetch()


def test_fetch_maps_every_job_in_the_board() -> None:
    jobs = _fetch_fixture_jobs()
    assert len(jobs) == 3
    assert all(isinstance(job, NormalizedJob) for job in jobs)
    assert all(job.source_type == "greenhouse" for job in jobs)
    assert all(job.company_name == "Example Co" for job in jobs)


def test_maps_new_grad_job_fields() -> None:
    jobs = _fetch_fixture_jobs()
    new_grad = next(job for job in jobs if job.source_job_id == "5658822003")

    assert new_grad.title == "Software Engineer, New Grad 2026"
    assert new_grad.location_text == "New York, NY"
    assert new_grad.application_url == "https://boards.greenhouse.io/exampleco/jobs/5658822003"
    assert new_grad.source_url == new_grad.application_url
    assert "new grad" in new_grad.description_plain
    assert "<" not in new_grad.description_plain
    assert new_grad.source_published_at == datetime(2026, 1, 14, 8, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert new_grad.source_updated_at == datetime(2026, 1, 15, 9, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert new_grad.raw_payload["id"] == 5658822003


def test_first_published_missing_maps_to_none() -> None:
    jobs = _fetch_fixture_jobs()
    senior = next(job for job in jobs if job.source_job_id == "5658822004")
    assert senior.source_published_at is None
    assert senior.source_updated_at is not None


def test_offices_used_as_location_fallback_when_location_absent() -> None:
    jobs = _fetch_fixture_jobs()
    backend = next(job for job in jobs if job.source_job_id == "5658822005")
    assert backend.location_text == "Chicago, IL"


def test_parse_timestamp_handles_missing_and_malformed_values() -> None:
    assert _parse_timestamp(None) is None
    assert _parse_timestamp("") is None
    assert _parse_timestamp("not-a-timestamp") is None
    assert _parse_timestamp("2026-01-14T08:00:00-05:00") is not None


def test_strip_html_to_text_removes_tags_and_collapses_whitespace() -> None:
    html = "<p>Hello   <strong>World</strong></p>\n<p>Second paragraph.</p>"
    assert strip_html_to_text(html) == "Hello World Second paragraph."


def test_strip_html_to_text_handles_blank_input() -> None:
    assert strip_html_to_text("") == ""
