"""Greenhouse Job Board API adapter.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 6.1: a public,
unauthenticated GET endpoint -- no API key needed.
``GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true``

``company_name`` comes from the source registry entry (a constructor
argument here in Checkpoint 1; the registry YAML itself is a later slice),
not the payload -- the Greenhouse board API does not return a company name
field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from swetrack.domains.jobs.adapters.base import strip_html_to_text
from swetrack.domains.jobs.schemas import NormalizedJob

_USER_AGENT = "SWETrack-JobRadar/0.1 (personal, non-commercial job search tool)"
_DEFAULT_TIMEOUT_SECONDS = 10.0


class GreenhouseAdapter:
    """Fetches every open job from one company's Greenhouse job board."""

    source_type = "greenhouse"

    def __init__(
        self,
        board_token: str,
        company_name: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.board_token = board_token
        self.company_name = company_name
        self._client = client
        self._timeout = timeout

    def fetch(self) -> list[NormalizedJob]:
        """GET the board's current job list and map every job to a NormalizedJob."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"
        client = self._client or httpx.Client(timeout=self._timeout, headers={"User-Agent": _USER_AGENT})
        owns_client = self._client is None
        try:
            response = client.get(url, params={"content": "true"})
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                client.close()
        return [self._to_normalized_job(job) for job in payload.get("jobs", [])]

    def _to_normalized_job(self, job: dict[str, Any]) -> NormalizedJob:
        location = job.get("location") or {}
        offices = job.get("offices") or []
        location_text = location.get("name") or (offices[0].get("name") if offices else "") or ""
        url = job.get("absolute_url", "")

        return NormalizedJob(
            source_type=self.source_type,
            source_job_id=str(job["id"]),
            company_name=self.company_name,
            title=job.get("title", ""),
            location_text=location_text,
            description_plain=strip_html_to_text(job.get("content", "")),
            application_url=url,
            source_url=url,
            source_published_at=_parse_timestamp(job.get("first_published")),
            source_updated_at=_parse_timestamp(job.get("updated_at")),
            raw_payload=job,
        )


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse a Greenhouse ISO-8601 timestamp, or None for missing/malformed input.

    Never raises: this is untrusted external data, and one unexpected date
    format on one job must not fail an entire sync.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
