"""Loading and validation of the candidate eligibility profile.

Mirrors opportunities/config.py's load_candidate_profile pattern: YAML in,
a validated Pydantic model out. Kept separate from
opportunities.models.CandidateProfile -- see
docs/job-radar-integration-plan.md Section 3.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from swetrack.domains.jobs.schemas import CandidateEligibilityProfile
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_CANDIDATE_CONFIG_PATH = find_repo_root() / "config" / "candidate.example.yaml"


class CandidateConfigError(ValueError):
    """Raised when the candidate eligibility profile YAML fails to load or validate."""


def load_candidate_eligibility_profile(
    path: str | Path = DEFAULT_CANDIDATE_CONFIG_PATH,
) -> CandidateEligibilityProfile:
    """Load and validate the candidate eligibility profile from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise CandidateConfigError(f"Candidate eligibility profile file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    try:
        return CandidateEligibilityProfile.model_validate(raw)
    except ValidationError as exc:
        raise CandidateConfigError(f"Invalid candidate eligibility profile at {path}: {exc}") from exc
