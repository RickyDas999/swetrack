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

from typing import Any

import httpx

from swetrack.domains.jobs.adapters.base import (
    DEFAULT_TIMEOUT_SECONDS,
    http_get_json,
    parse_iso_timestamp,
    strip_html_to_text,
)
from swetrack.domains.jobs.schemas import NormalizedJob


class GreenhouseAdapter:
    """Fetches every open job from one company's Greenhouse job board."""

    source_type = "greenhouse"

    def __init__(
        self,
        board_token: str,
        company_name: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.board_token = board_token
        self.company_name = company_name
        self._client = client
        self._timeout = timeout

    def fetch(self) -> list[NormalizedJob]:
        """GET the board's current job list and map every job to a NormalizedJob."""
        payload = http_get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs",
            params={"content": "true"},
            client=self._client,
            timeout=self._timeout,
        )
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
            source_published_at=parse_iso_timestamp(job.get("first_published")),
            source_updated_at=parse_iso_timestamp(job.get("updated_at")),
            raw_payload=job,
        )
