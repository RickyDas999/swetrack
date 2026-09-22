"""Deterministic new-grad eligibility classifier.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 9. Returns a decision,
confidence, and the exact matched phrases -- never an LLM call ("Never ask
an LLM to make an unexplained eligibility decision"). Does not reject a job
merely because "new grad" is absent from the title, and marks a job
``uncertain`` (not ``ineligible``) when positive and negative signals
conflict, rather than guessing.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from swetrack.domains.jobs.schemas import CandidateEligibilityProfile

EligibilityStatus = Literal["eligible", "uncertain", "ineligible"]

CLASSIFIER_VERSION = "eligibility-v1"

_MAX_YEARS_EXPERIENCE = 3

_POSITIVE_PHRASES = [
    "new grad",
    "new graduate",
    "university graduate",
    "recent graduate",
    "entry level",
    "entry-level",
    "early career",
    "campus hire",
    "university hire",
    "associate software engineer",
]
_POSITIVE_TITLE_PATTERNS = [
    re.compile(r"\bsoftware engineer i\b", re.IGNORECASE),
    re.compile(r"\bsoftware developer i\b", re.IGNORECASE),
]
_LOW_EXPERIENCE_PATTERNS = [
    re.compile(r"\b0\s*(?:-|to)\s*2\s*years?\b", re.IGNORECASE),
    re.compile(r"\b0\s*(?:-|to)\s*3\s*years?\b", re.IGNORECASE),
]

_DEFAULT_EXCLUDED_LEVELS = ["senior", "staff", "principal", "lead", "manager", "architect", "director"]
_INTERNSHIP_TITLE_PATTERN = re.compile(r"\b(?:intern|internship|co-?op)\b", re.IGNORECASE)
_MIN_EXPERIENCE_PATTERN = re.compile(r"(\d+)\s*\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE)
_CLEARANCE_PATTERN = re.compile(r"\bsecurity clearance\b", re.IGNORECASE)
_CLOSED_PATTERN = re.compile(
    r"\b(?:no longer accepting applications|position (?:has been |is )?(?:filled|closed))\b", re.IGNORECASE
)


class EligibilityAssessment(BaseModel):
    """One job's new-grad eligibility decision, with reasons and matched phrases."""

    model_config = ConfigDict(frozen=True)

    status: EligibilityStatus
    confidence: float = Field(ge=0.0, le=1.0)
    positive_signals: list[str]
    negative_signals: list[str]
    reasons: list[str]
    classifier_version: str = CLASSIFIER_VERSION


def classify_new_grad_eligibility(
    *, title: str, description: str, candidate: CandidateEligibilityProfile
) -> EligibilityAssessment:
    """Deterministic new-grad eligibility decision for one job's title/description."""
    title_lower = title.lower()
    text = f"{title} {description}"
    text_lower = text.lower()

    positive: list[str] = []
    negative: list[str] = []
    reasons: list[str] = []

    for phrase in _POSITIVE_PHRASES:
        if phrase in text_lower:
            positive.append(phrase)
    for pattern in _POSITIVE_TITLE_PATTERNS:
        match = pattern.search(title)
        if match:
            positive.append(match.group(0).lower())
    for pattern in _LOW_EXPERIENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            positive.append(match.group(0).lower())

    for phrase in (f"{candidate.graduation_year} graduate", f"class of {candidate.graduation_year}"):
        if phrase in text_lower:
            positive.append(phrase)

    excluded_levels = [level.lower() for level in candidate.excluded_levels] or _DEFAULT_EXCLUDED_LEVELS
    for level in excluded_levels:
        # Title-only: a body mention like "collaborate with senior
        # engineers" should not disqualify a genuinely entry-level posting.
        if re.search(rf"\b{re.escape(level)}\b", title_lower):
            negative.append(level)
            reasons.append(f"Title contains excluded level {level!r}")

    if _INTERNSHIP_TITLE_PATTERN.search(title):
        negative.append("internship/co-op title")
        reasons.append("Title indicates an internship/co-op, not a full-time new-grad role")

    for match in _MIN_EXPERIENCE_PATTERN.finditer(text):
        years = int(match.group(1))
        if years > _MAX_YEARS_EXPERIENCE:
            negative.append(f"{years}+ years experience required")
            reasons.append(f"Requires {years}+ years of experience, above the new-grad threshold")

    if _CLEARANCE_PATTERN.search(text):
        negative.append("security clearance required")
        reasons.append("Requires a security clearance; candidate profile does not confirm eligibility")

    if _CLOSED_PATTERN.search(text):
        negative.append("posting indicates it is closed/filled")
        reasons.append("Description text indicates the role is no longer accepting applications")

    if negative and positive:
        status: EligibilityStatus = "uncertain"
        confidence = 0.5
        reasons.append("Both new-grad and disqualifying signals present; needs manual review")
    elif negative:
        status = "ineligible"
        confidence = min(1.0, 0.6 + 0.15 * len(negative))
    elif positive:
        status = "eligible"
        confidence = min(1.0, 0.6 + 0.1 * len(positive))
        reasons.append("New-grad signals found with no disqualifying signals")
    else:
        status = "uncertain"
        confidence = 0.4
        reasons.append("No clear new-grad or disqualifying signals found; title alone is not sufficient to reject")

    return EligibilityAssessment(
        status=status,
        confidence=round(confidence, 2),
        positive_signals=sorted(set(positive)),
        negative_signals=sorted(set(negative)),
        reasons=reasons,
    )
