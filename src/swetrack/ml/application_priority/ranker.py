"""Explainable heuristic Application Priority ranker (CLAUDE.md Phase 14).

Pure functions only -- no database or business-logic imports here, mirroring
``ml/study_ranking/ranker.py``'s separation.

CLAUDE.md's full component list is role fit, readiness, user preference,
deadline urgency, company interest, location, and compensation. All six are
implemented here (location folds into ``user_preference`` alongside role,
matching ``opportunities.ranking.base.build_match_reasons``'s existing
matched_roles/matched_locations pair). Each is backed by a real, collected
data source -- ``JobRecord.compensation_min/max``/``application_deadline``
and ``CandidateProfile.preferred_companies``/``minimum_compensation`` (added
alongside this module) -- so nothing here is an invented number standing in
for data that doesn't exist yet.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

# Days until a deadline at which urgency has decayed to ~37% (1/e) of its
# peak. A configured constant, not fit to any data -- see bkt.py's
# DEFAULT_PARAMETERS docstring for the same "configured, not learned"
# distinction.
_DEFAULT_DEADLINE_HALF_LIFE_DAYS = 14.0


class ApplicationPriorityWeights(BaseModel):
    """Configurable weights combining the six priority components into one score.

    Sums to 1.0 so the combined score stays in [0, 1].
    """

    model_config = ConfigDict(frozen=True)

    role_fit: float = Field(ge=0.0, le=1.0, default=0.30)
    readiness: float = Field(ge=0.0, le=1.0, default=0.30)
    user_preference: float = Field(ge=0.0, le=1.0, default=0.15)
    company_interest: float = Field(ge=0.0, le=1.0, default=0.10)
    compensation_fit: float = Field(ge=0.0, le=1.0, default=0.10)
    deadline_urgency: float = Field(ge=0.0, le=1.0, default=0.05)


DEFAULT_WEIGHTS = ApplicationPriorityWeights()


class ApplicationPriorityComponents(BaseModel):
    """The per-component breakdown behind one application's priority score."""

    model_config = ConfigDict(frozen=True)

    role_fit: float = Field(ge=0.0, le=1.0)
    readiness: float = Field(ge=0.0, le=1.0)
    user_preference: float = Field(ge=0.0, le=1.0)
    company_interest: float = Field(ge=0.0, le=1.0)
    compensation_fit: float = Field(ge=0.0, le=1.0)
    deadline_urgency: float = Field(ge=0.0, le=1.0)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def compute_role_fit(fit_score: float) -> float:
    """Clamp a ranker's raw similarity score into [0, 1].

    Embedding cosine similarity can be negative for unrelated text; TF-IDF
    cannot, but is clamped identically for a uniform component range.
    """
    return _clamp(fit_score)


def compute_preference_match(*, has_preference: bool, matched: bool) -> float:
    """One preference dimension's (role, location, or company) contribution.

    Neutral (0.5) when the candidate stated no preference on this dimension
    at all -- there is nothing to have matched or missed. 1.0 when a stated
    preference matched the job, 0.0 when it did not.
    """
    if not has_preference:
        return 0.5
    return 1.0 if matched else 0.0


def compute_user_preference(*, role_preference_match: float, location_preference_match: float) -> float:
    """Combine the role- and location-preference dimensions into one component."""
    return (role_preference_match + location_preference_match) / 2.0


def compute_compensation_fit(*, job_compensation_max: int | None, candidate_minimum: int | None) -> float:
    """How well a job's top-of-range pay clears the candidate's stated minimum.

    Neutral (0.5) when either side has no data to compare -- the candidate
    stated no minimum, or the posting carries no compensation figure. 1.0
    when the job's max clears the candidate's minimum, 0.0 when it falls
    short. Compared against the job's *max* (not min) since that is the
    best realistic outcome a candidate could negotiate toward.
    """
    if candidate_minimum is None or job_compensation_max is None:
        return 0.5
    return 1.0 if job_compensation_max >= candidate_minimum else 0.0


def compute_deadline_urgency(
    days_until_deadline: float | None, *, half_life_days: float = _DEFAULT_DEADLINE_HALF_LIFE_DAYS
) -> float:
    """How soon a deadline is approaching: ~0.0 (far off or none) rising to 1.0 (imminent).

    ``None`` (no known deadline) and a deadline that has already passed both
    return 0.0 -- there is no known pressure to act in the first case, and
    nothing actionable left to rush in the second.
    """
    if days_until_deadline is None or days_until_deadline <= 0:
        return 0.0
    return _clamp(math.exp(-days_until_deadline / half_life_days))


def score_application(
    components: ApplicationPriorityComponents, weights: ApplicationPriorityWeights = DEFAULT_WEIGHTS
) -> float:
    """Combine one application's components into a single explainable priority score."""
    raw = (
        weights.role_fit * components.role_fit
        + weights.readiness * components.readiness
        + weights.user_preference * components.user_preference
        + weights.company_interest * components.company_interest
        + weights.compensation_fit * components.compensation_fit
        + weights.deadline_urgency * components.deadline_urgency
    )
    return _clamp(raw)
