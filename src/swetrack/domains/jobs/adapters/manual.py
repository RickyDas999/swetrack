"""Manual URL / pasted-JD import: the guaranteed fallback for ATS platforms with no public API.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 6, Tier 2: "Manual URL/paste
import as a guaranteed fallback for Workday and unsupported ATS pages."
Unlike the polling adapters, there is nothing to fetch -- the user supplies
one job's details directly, so this does not belong in the recurring-poll
source registry (see ``schemas.PollableSourceType``).
"""

from __future__ import annotations

import hashlib

from swetrack.domains.jobs.adapters.base import strip_html_to_text
from swetrack.domains.jobs.schemas import NormalizedJob


class ManualAdapter:
    """One manually-imported job. ``fetch()`` always returns exactly one job."""

    source_type = "manual"

    def __init__(
        self,
        *,
        url: str,
        company_name: str,
        title: str,
        description: str = "",
        location: str = "",
        source_job_id: str | None = None,
    ) -> None:
        if not url.strip():
            raise ValueError("Manual import requires a non-blank job URL")
        self.url = url.strip()
        self.company_name = company_name
        self.title = title
        self.description = description
        self.location = location
        # Defaults to a stable hash of the URL so re-importing the same URL
        # twice produces the same identity, matching every other adapter's
        # (source_type, source_job_id) dedup key (Checkpoint 2).
        self.source_job_id = source_job_id or hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]

    def fetch(self) -> list[NormalizedJob]:
        return [
            NormalizedJob(
                source_type=self.source_type,
                source_job_id=self.source_job_id,
                company_name=self.company_name,
                title=self.title,
                location_text=self.location,
                description_plain=strip_html_to_text(self.description),
                application_url=self.url,
                source_url=self.url,
                raw_payload={"url": self.url, "pasted_description": self.description},
            )
        ]
