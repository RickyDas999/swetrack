"""Ashby public Job Postings API adapter.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 6.3: a public,
unauthenticated GET endpoint -- no API key needed.
``GET https://api.ashbyhq.com/posting-api/job-board/{board_name}?includeCompensation=true``
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


class AshbyAdapter:
    """Fetches every open posting from one company's Ashby job board."""

    source_type = "ashby"

    def __init__(
        self,
        board_name: str,
        company_name: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.board_name = board_name
        self.company_name = company_name
        self._client = client
        self._timeout = timeout

    def fetch(self) -> list[NormalizedJob]:
        """GET the board's current job list and map every job to a NormalizedJob."""
        payload = http_get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{self.board_name}",
            params={"includeCompensation": "true"},
            client=self._client,
            timeout=self._timeout,
        )
        return [self._to_normalized_job(job) for job in payload.get("jobs", [])]

    def _to_normalized_job(self, job: dict[str, Any]) -> NormalizedJob:
        # Ashby sometimes ships descriptionPlain directly; fall back to
        # stripping descriptionHtml when it doesn't.
        description_plain = job.get("descriptionPlain") or strip_html_to_text(job.get("descriptionHtml", ""))
        url = job.get("jobUrl", "")

        return NormalizedJob(
            source_type=self.source_type,
            source_job_id=str(job["id"]),
            company_name=self.company_name,
            title=job.get("title", ""),
            location_text=job.get("location", ""),
            # Ashby's own field values (e.g. "Remote", "FullTime") -- not
            # remapped to a shared vocabulary here; cross-source
            # canonicalization is domains/jobs/normalize.py, a later
            # checkpoint.
            workplace_type=job.get("workplaceType"),
            employment_type=job.get("employmentType"),
            description_plain=description_plain,
            application_url=url,
            source_url=url,
            source_published_at=parse_iso_timestamp(job.get("publishedAt")),
            source_updated_at=parse_iso_timestamp(job.get("updatedAt")),
            raw_payload=job,
        )
