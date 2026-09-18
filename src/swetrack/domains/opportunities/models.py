"""Pydantic schemas for candidate profiles, job records, and API payloads.

These models are the single validated representation of inputs and outputs
shared by both rankers, the CLI scripts, and the FastAPI service.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RankerName = Literal["tfidf", "embedding"]
JobSource = Literal["sample", "synthetic"]


def _clean_str_list(value: object) -> list[str]:
    """Coerce a comma-separated string or a list into a de-blanked str list."""
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        raise TypeError(f"Expected str or list, got {type(value).__name__}")
    return [str(item).strip() for item in items if str(item).strip()]


class CandidateProfile(BaseModel):
    """A candidate's skills, experience, and preferences used to build a query."""

    skills: list[str] = Field(..., min_length=1)
    experience: str = Field(..., min_length=1)
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_companies: list[str] = Field(default_factory=list)
    minimum_compensation: int | None = Field(default=None, ge=0)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("skills", "preferred_roles", "preferred_locations", "preferred_companies", "keywords", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _clean_str_list(value)

    @field_validator("experience")
    @classmethod
    def _experience_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("experience must not be blank")
        return cleaned

    @field_validator("skills")
    @classmethod
    def _skills_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("skills must contain at least one non-blank entry")
        return value


class JobRecord(BaseModel):
    """A single job posting, marked with sample/synthetic provenance."""

    job_id: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    location: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_level: str = ""
    url: str = ""
    source: JobSource = "synthetic"
    compensation_min: int | None = Field(default=None, ge=0)
    compensation_max: int | None = Field(default=None, ge=0)
    application_deadline: date | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _normalize_skills(cls, value: object) -> list[str]:
        return _clean_str_list(value)

    @field_validator("job_id", "company", "title")
    @classmethod
    def _required_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required field must not be blank")
        return cleaned

    @field_validator("location", "description", "experience_level", "url", mode="before")
    @classmethod
    def _optional_str(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("compensation_min", "compensation_max", "application_deadline", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """CSV rows hand in "" (not a missing key) for an unfilled cell."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _compensation_range_is_ordered(self) -> "JobRecord":
        if self.compensation_min is not None and self.compensation_max is not None:
            if self.compensation_min > self.compensation_max:
                raise ValueError("compensation_min must not exceed compensation_max")
        return self


class MatchReasons(BaseModel):
    """Structured, human-readable explanation for one recommendation."""

    matched_skills: list[str] = Field(default_factory=list)
    matched_roles: list[str] = Field(default_factory=list)
    matched_locations: list[str] = Field(default_factory=list)
    matched_companies: list[str] = Field(default_factory=list)

    def as_text(self) -> list[str]:
        """Render structured overlap fields as short human-readable strings."""
        lines: list[str] = []
        if self.matched_skills:
            lines.append(f"Matched skills: {', '.join(self.matched_skills)}")
        if self.matched_roles:
            lines.append(f"Preferred role match: {', '.join(self.matched_roles)}")
        if self.matched_locations:
            lines.append(f"Preferred location match: {', '.join(self.matched_locations)}")
        if self.matched_companies:
            lines.append(f"Preferred company match: {', '.join(self.matched_companies)}")
        if not lines:
            lines.append("No structured skill, role, location, or company overlap detected.")
        return lines


class RecommendationItem(BaseModel):
    """One ranked job result returned by the API and CLI."""

    rank: int
    job: JobRecord
    ranker: RankerName
    score: float
    reasons: list[str]


class RecommendRequest(BaseModel):
    """POST /recommend request body.

    ``profile`` is optional so the API works without a private resume, but
    the example profile is only ever substituted when the caller explicitly
    sets ``use_example_profile: true`` -- it is never a silent default.
    """

    profile: CandidateProfile | None = None
    use_example_profile: bool = False
    ranker: RankerName = "tfidf"
    top_k: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def _profile_or_explicit_example(self) -> "RecommendRequest":
        if self.profile is None and not self.use_example_profile:
            raise ValueError(
                "Provide 'profile', or set 'use_example_profile': true to use the example candidate profile."
            )
        return self


class RecommendResponse(BaseModel):
    """POST /recommend response body."""

    ranker: RankerName
    top_k: int
    results: list[RecommendationItem]


class HealthResponse(BaseModel):
    """GET /health response body."""

    status: Literal["ok"] = "ok"
    version: str
