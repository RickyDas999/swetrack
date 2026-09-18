"""Validated, immutable read/write schemas for interview tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# CLAUDE.md Phase 13's round types.
RoundType = Literal["recruiter", "oa", "coding", "system_design", "behavioral", "hiring_manager", "final"]

# "pending" covers an interview logged before its outcome is known; SkillEvents
# are only emitted once result is "passed" or "failed" (see services.create_interview).
InterviewResult = Literal["passed", "failed", "pending"]


class Interview(BaseModel):
    """One logged interview round."""

    model_config = ConfigDict(frozen=True)

    id: str
    application_id: str | None
    company: str
    role: str
    round_type: RoundType
    date: datetime
    skills_tested: list[str]
    result: InterviewResult
    notes: str = ""
    feedback: str = ""
    created_at: datetime


class CreateInterviewRequest(BaseModel):
    """Request body for ``POST /interviews``."""

    application_id: str | None = None
    company: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    round_type: RoundType
    date: datetime
    skills_tested: list[str] = Field(default_factory=list)
    result: InterviewResult = "pending"
    notes: str = ""
    feedback: str = ""
