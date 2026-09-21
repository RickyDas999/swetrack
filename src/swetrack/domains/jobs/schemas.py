"""NormalizedJob and the source registry entry schema.

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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceType = Literal["greenhouse", "lever", "ashby", "manual"]

# Manual import is a one-off, user-triggered flow (one job at a time via a
# URL/pasted JD), not something a recurring poll registry entry names --
# see adapters/manual.py and SWETrack_Job_Radar_Claude_Code_Handoff.md
# Section 6 (registry vs. manual import are two separate bullets there).
PollableSourceType = Literal["greenhouse", "lever", "ashby"]
LeverRegion = Literal["global", "eu"]

_REQUIRED_IDENTIFIER_FIELD: dict[str, str] = {
    "greenhouse": "token",
    "lever": "site",
    "ashby": "board_name",
}


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


class SourceRegistryEntry(BaseModel):
    """One reviewed, recurring-poll ATS source (SWETrack_Job_Radar_Claude_Code_Handoff.md Section 6).

    Exactly one of ``token``/``site``/``board_name`` is required, matching
    ``adapter`` -- validated below rather than modeled as three separate
    subtypes, since the registry YAML is meant to read as one flat list a
    human reviews and edits directly.
    """

    company: str = Field(..., min_length=1)
    adapter: PollableSourceType
    enabled: bool = True
    poll_minutes: int = Field(default=15, ge=1)
    token: str | None = None
    site: str | None = None
    region: LeverRegion = "global"
    board_name: str | None = None

    @model_validator(mode="after")
    def _identifier_matches_adapter(self) -> "SourceRegistryEntry":
        required_field = _REQUIRED_IDENTIFIER_FIELD[self.adapter]
        if not getattr(self, required_field):
            raise ValueError(f"adapter={self.adapter!r} requires a non-blank {required_field!r} field")
        return self


class SyncResult(BaseModel):
    """Summary of one ``sync_source()`` call.

    SWETrack_Job_Radar_Claude_Code_Handoff.md's "Add sync metrics and
    structured logs" (Checkpoint 2).
    """

    model_config = ConfigDict(frozen=True)

    source_type: str
    total_fetched: int = Field(ge=0)
    new_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
