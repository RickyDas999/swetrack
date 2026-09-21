"""ATS adapter payload -> NormalizedJob mapping (Job Radar Checkpoint 1).

Uses httpx.MockTransport so each adapter's fetch() exercises its real HTTP
call path end-to-end with zero live network access, per
SWETrack_Job_Radar_Claude_Code_Handoff.md Section 17: "Mock HTTP using
recorded/redacted fixtures; CI must not depend on live ATS availability."
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from swetrack.domains.jobs.adapters.ashby import AshbyAdapter
from swetrack.domains.jobs.adapters.base import parse_iso_timestamp, strip_html_to_text
from swetrack.domains.jobs.adapters.greenhouse import GreenhouseAdapter
from swetrack.domains.jobs.adapters.lever import LeverAdapter
from swetrack.domains.jobs.adapters.manual import ManualAdapter
from swetrack.domains.jobs.schemas import NormalizedJob

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ats"


def _load_fixture(name: str) -> object:
    return json.loads((_FIXTURES_DIR / name).read_text())


def _mock_transport(path: str, params: dict[str, str], payload: object) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == path
        for key, value in params.items():
            assert request.url.params[key] == value
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------

_GREENHOUSE_PAYLOAD = _load_fixture("greenhouse_sample.json")


def _fetch_greenhouse_fixture_jobs() -> list[NormalizedJob]:
    transport = _mock_transport("/v1/boards/exampleco/jobs", {"content": "true"}, _GREENHOUSE_PAYLOAD)
    client = httpx.Client(transport=transport)
    adapter = GreenhouseAdapter("exampleco", "Example Co", client=client)
    return adapter.fetch()


def test_greenhouse_fetch_maps_every_job_in_the_board() -> None:
    jobs = _fetch_greenhouse_fixture_jobs()
    assert len(jobs) == 3
    assert all(isinstance(job, NormalizedJob) for job in jobs)
    assert all(job.source_type == "greenhouse" for job in jobs)
    assert all(job.company_name == "Example Co" for job in jobs)


def test_greenhouse_maps_new_grad_job_fields() -> None:
    jobs = _fetch_greenhouse_fixture_jobs()
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


def test_greenhouse_first_published_missing_maps_to_none() -> None:
    jobs = _fetch_greenhouse_fixture_jobs()
    senior = next(job for job in jobs if job.source_job_id == "5658822004")
    assert senior.source_published_at is None
    assert senior.source_updated_at is not None


def test_greenhouse_offices_used_as_location_fallback_when_location_absent() -> None:
    jobs = _fetch_greenhouse_fixture_jobs()
    backend = next(job for job in jobs if job.source_job_id == "5658822005")
    assert backend.location_text == "Chicago, IL"


# ---------------------------------------------------------------------------
# Lever
# ---------------------------------------------------------------------------

_LEVER_PAYLOAD = _load_fixture("lever_sample.json")


def _fetch_lever_fixture_jobs() -> list[NormalizedJob]:
    transport = _mock_transport("/v0/postings/exampleco", {"mode": "json"}, _LEVER_PAYLOAD)
    client = httpx.Client(transport=transport)
    adapter = LeverAdapter("exampleco", "Example Co", client=client)
    return adapter.fetch()


def test_lever_fetch_maps_every_posting() -> None:
    jobs = _fetch_lever_fixture_jobs()
    assert len(jobs) == 2
    assert all(isinstance(job, NormalizedJob) for job in jobs)
    assert all(job.source_type == "lever" for job in jobs)
    assert all(job.company_name == "Example Co" for job in jobs)


def test_lever_maps_new_grad_posting_fields() -> None:
    jobs = _fetch_lever_fixture_jobs()
    new_grad = next(job for job in jobs if job.source_job_id == "8e4a2b6c-1111-4a2b-9c3d-abcdef123456")

    assert new_grad.title == "Software Engineer, New Grad"
    assert new_grad.location_text == "New York"
    assert new_grad.workplace_type == "remote"
    assert new_grad.employment_type == "Full-time"
    assert new_grad.application_url.endswith("/apply")
    assert new_grad.source_url == "https://jobs.lever.co/exampleco/8e4a2b6c-1111-4a2b-9c3d-abcdef123456"
    assert "new grad" in new_grad.description_plain
    assert "<" not in new_grad.description_plain
    assert new_grad.source_published_at == datetime.fromtimestamp(1768435200000 / 1000, tz=timezone.utc)
    assert new_grad.source_updated_at is None
    assert new_grad.raw_payload["id"] == "8e4a2b6c-1111-4a2b-9c3d-abcdef123456"


def test_lever_apply_url_falls_back_to_hosted_url_when_absent() -> None:
    jobs = _fetch_lever_fixture_jobs()
    staff = next(job for job in jobs if job.source_job_id == "8e4a2b6c-2222-4a2b-9c3d-abcdef123456")
    assert staff.application_url == staff.source_url
    assert staff.application_url == "https://jobs.lever.co/exampleco/8e4a2b6c-2222-4a2b-9c3d-abcdef123456"


# ---------------------------------------------------------------------------
# Ashby
# ---------------------------------------------------------------------------

_ASHBY_PAYLOAD = _load_fixture("ashby_sample.json")


def _fetch_ashby_fixture_jobs() -> list[NormalizedJob]:
    transport = _mock_transport(
        "/posting-api/job-board/exampleai", {"includeCompensation": "true"}, _ASHBY_PAYLOAD
    )
    client = httpx.Client(transport=transport)
    adapter = AshbyAdapter("exampleai", "Example AI", client=client)
    return adapter.fetch()


def test_ashby_fetch_maps_every_job() -> None:
    jobs = _fetch_ashby_fixture_jobs()
    assert len(jobs) == 2
    assert all(isinstance(job, NormalizedJob) for job in jobs)
    assert all(job.source_type == "ashby" for job in jobs)
    assert all(job.company_name == "Example AI" for job in jobs)


def test_ashby_maps_new_grad_job_fields() -> None:
    jobs = _fetch_ashby_fixture_jobs()
    new_grad = next(job for job in jobs if job.source_job_id == "f1e2d3c4-b5a6-4978-8899-aabbccddeeff")

    assert new_grad.title == "Software Engineer, New Grad"
    assert new_grad.location_text == "Chicago, IL"
    assert new_grad.workplace_type == "Hybrid"
    assert new_grad.employment_type == "FullTime"
    assert "new grad" in new_grad.description_plain
    assert "<" not in new_grad.description_plain
    assert new_grad.source_published_at == datetime(2026, 1, 14, 8, 0, tzinfo=timezone.utc)
    assert new_grad.source_updated_at == datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


def test_ashby_uses_description_plain_when_present_instead_of_stripping_html() -> None:
    jobs = _fetch_ashby_fixture_jobs()
    principal = next(job for job in jobs if job.source_job_id == "f1e2d3c4-b5a6-4978-8899-aabbccddeef0")
    assert principal.description_plain == "12+ years of experience required."


def test_ashby_published_at_missing_maps_to_none() -> None:
    jobs = _fetch_ashby_fixture_jobs()
    principal = next(job for job in jobs if job.source_job_id == "f1e2d3c4-b5a6-4978-8899-aabbccddeef0")
    assert principal.source_published_at is None
    assert principal.source_updated_at is not None


# ---------------------------------------------------------------------------
# Manual import
# ---------------------------------------------------------------------------


def test_manual_adapter_produces_one_normalized_job() -> None:
    adapter = ManualAdapter(
        url="https://example.com/careers/12345",
        company_name="Example Co",
        title="Software Engineer, New Grad",
        description="<p>New grad role.</p>",
        location="Austin, TX",
    )
    jobs = adapter.fetch()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_type == "manual"
    assert job.application_url == "https://example.com/careers/12345"
    assert job.source_url == job.application_url
    assert job.description_plain == "New grad role."
    assert job.location_text == "Austin, TX"


def test_manual_adapter_source_job_id_is_stable_for_the_same_url() -> None:
    first = ManualAdapter(url="https://example.com/careers/12345", company_name="Example Co", title="A")
    second = ManualAdapter(url="https://example.com/careers/12345", company_name="Example Co", title="A")
    assert first.source_job_id == second.source_job_id


def test_manual_adapter_rejects_blank_url() -> None:
    with pytest.raises(ValueError):
        ManualAdapter(url="   ", company_name="Example Co", title="A")


# ---------------------------------------------------------------------------
# Shared helpers (base.py)
# ---------------------------------------------------------------------------


def test_parse_iso_timestamp_handles_missing_and_malformed_values() -> None:
    assert parse_iso_timestamp(None) is None
    assert parse_iso_timestamp("") is None
    assert parse_iso_timestamp("not-a-timestamp") is None
    assert parse_iso_timestamp("2026-01-14T08:00:00-05:00") is not None


def test_strip_html_to_text_removes_tags_and_collapses_whitespace() -> None:
    html = "<p>Hello   <strong>World</strong></p>\n<p>Second paragraph.</p>"
    assert strip_html_to_text(html) == "Hello World Second paragraph."


def test_strip_html_to_text_handles_blank_input() -> None:
    assert strip_html_to_text("") == ""
