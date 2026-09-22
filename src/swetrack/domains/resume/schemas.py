"""Evidence library and resume-tailoring output schemas.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 7 (resume_evidence table)
and Section 11 (tailoring pipeline outputs). ``EvidenceItem`` is the unit
every tailored resume claim must map back to -- CLAUDE.md's truth gate:
"Every generated claim must include evidence_id."
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceSection = Literal["experience", "project", "education", "skill"]


class EvidenceItem(BaseModel):
    """One resume fact: a bullet, an education line, or a skill-list entry.

    ``verified`` defaults to True (checked into evidence.yaml means a human
    approved it) but can be set False to flag a claim that needs review --
    e.g. one that no longer matches the actual, current state of a linked
    project (see docs: the SWETrack project bullet's PostgreSQL/React
    claims are flagged this way as of Checkpoint 5).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1)
    section: EvidenceSection
    organization: str = Field(..., min_length=1)
    role: str = ""
    date_range: str = ""
    base_text: str = Field(..., min_length=1)
    supported_skills: list[str] = Field(default_factory=list)
    supported_metrics: list[str] = Field(default_factory=list)
    verified: bool = True
    enabled: bool = True
    review_note: str = ""


class RequirementExtraction(BaseModel):
    """Skills/keywords pulled from a job description, split by evidence-library coverage."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    required_skills: list[str]
    covered_skills: list[str]
    missing_skills: list[str]


class GapsReportEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    skill: str
    reason: str = "No verified evidence supports this skill; it will not be added to the resume."


class GapsReport(BaseModel):
    """Skills the job wants but the evidence library cannot honestly support.

    CLAUDE.md: "Missing job requirements belong in a gaps report, not in
    the resume" and "Never add a skill solely because it appears in the
    job description."
    """

    model_config = ConfigDict(frozen=True)

    job_id: str
    gaps: list[GapsReportEntry]


class ATSCoverageReport(BaseModel):
    """Transparent keyword coverage for one tailored resume -- never an "ATS pass probability"."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    covered_keywords: list[str]
    supported_but_unused_keywords: list[str]
    unsupported_keywords: list[str]


class SelectedEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    relevance_score: float = Field(ge=0.0)
    matched_skills: list[str]


class TailoredResumeResult(BaseModel):
    """One deterministic tailoring pass's full, explainable output."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    selected_evidence: list[SelectedEvidence]
    gaps: GapsReport
    ats_coverage: ATSCoverageReport
    latex_path: str
    generator_version: str


class ResumeDiffEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    organization: str
    change: Literal["kept", "reordered", "excluded"]


class ResumeDiff(BaseModel):
    """What changed between the full base resume and one tailored variant.

    Selection/reordering only -- CLAUDE.md: "Never alter dates, titles,
    employers, metrics, scale, or deployment status without approved
    evidence," so no entry here should ever represent a text change.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str
    entries: list[ResumeDiffEntry]
