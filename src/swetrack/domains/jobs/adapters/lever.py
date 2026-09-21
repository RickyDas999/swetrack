"""Lever Postings API adapter.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 6.2: a public,
unauthenticated GET endpoint -- no API key needed.
``GET https://api.lever.co/v0/postings/{site}?mode=json`` (``region="eu"``
uses ``api.eu.lever.co`` instead, per the handoff's source registry shape).

Unlike Greenhouse/Ashby, the response body is a bare JSON array of postings,
not wrapped in an object. Lever's public postings API also exposes no
last-modified timestamp -- ``createdAt`` is the only date it gives, so
``source_updated_at`` is always None here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from swetrack.domains.jobs.adapters.base import DEFAULT_TIMEOUT_SECONDS, http_get_json, strip_html_to_text
from swetrack.domains.jobs.schemas import NormalizedJob


class LeverAdapter:
    """Fetches every open posting from one company's Lever postings site."""

    source_type = "lever"

    def __init__(
        self,
        site: str,
        company_name: str,
        *,
        region: str = "global",
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.site = site
        self.company_name = company_name
        self.region = region
        self._client = client
        self._timeout = timeout

    def fetch(self) -> list[NormalizedJob]:
        """GET the site's current postings list and map every posting to a NormalizedJob."""
        host = "api.eu.lever.co" if self.region == "eu" else "api.lever.co"
        postings = http_get_json(
            f"https://{host}/v0/postings/{self.site}",
            params={"mode": "json"},
            client=self._client,
            timeout=self._timeout,
        )
        return [self._to_normalized_job(posting) for posting in postings]

    def _to_normalized_job(self, posting: dict[str, Any]) -> NormalizedJob:
        categories = posting.get("categories") or {}
        content = posting.get("content") or {}
        hosted_url = posting.get("hostedUrl", "")
        apply_url = posting.get("applyUrl") or hosted_url

        return NormalizedJob(
            source_type=self.source_type,
            source_job_id=str(posting["id"]),
            company_name=self.company_name,
            title=posting.get("text", ""),
            location_text=categories.get("location", ""),
            # Lever's own field values (e.g. "remote", "on-site") -- not
            # remapped to a shared vocabulary here; cross-source
            # canonicalization is domains/jobs/normalize.py, a later
            # checkpoint.
            workplace_type=posting.get("workplaceType"),
            employment_type=categories.get("commitment"),
            description_plain=strip_html_to_text(content.get("description", "")),
            application_url=apply_url,
            source_url=hosted_url,
            source_published_at=_parse_epoch_millis(posting.get("createdAt")),
            source_updated_at=None,
            raw_payload=posting,
        )


def _parse_epoch_millis(value: Any) -> datetime | None:
    """Parse a Lever epoch-milliseconds timestamp, or None for missing/malformed input."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
