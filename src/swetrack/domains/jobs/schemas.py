"""NormalizedJob: the single shape every job-source adapter returns.

Job Radar Checkpoint 1 (SWETrack_Job_Radar_Claude_Code_Handoff.md Sections
5-7). Adapter output only -- no database identity, first-seen tracking,
deduplication, or scoring here (that lands in domains/jobs/services.py in
Checkpoint 2). Every adapter (Greenhouse, Lever, Ashby, manual) maps its own
payload shape into this one Pydantic model so downstream code never needs to
know which source a job came from.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SourceType = Literal["greenhouse", "lever", "ashby", "manual"]


class NormalizedJob(BaseModel):
    """One job posting in the common shape every source adapter produces."""

    source_type: SourceType
    source_job_id: str = Field(..., min_length=1)
    company_name: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    location_text: str = ""
    workplace_type: str | None = None
    employment_type: str | None = None
    description_plain: str = ""
    application_url: str = ""
    source_url: str = ""
    source_published_at: datetime | None = None
    source_updated_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_job_id", "company_name", "title")
    @classmethod
    def _required_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required field must not be blank")
        return cleaned
