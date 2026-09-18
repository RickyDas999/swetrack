"""Explainable heuristic Application Priority ranker (CLAUDE.md Phase 14).

Pure functions only -- no database or business-logic imports here, mirroring
``ml/study_ranking/ranker.py``'s separation.

CLAUDE.md's full component list for Application Priority is role fit,
readiness, user preference, deadline urgency, company interest, location,
and compensation. Only ``role_fit``, ``readiness``, and ``user_preference``
are implemented: those are the only ones with a real, already-collected data
source today (``opportunities.readiness.compute_readiness`` and
``opportunities.ranking.base.build_match_reasons``'s role/location overlap).
``JobRecord`` carries no deadline or compensation field and there is no
captured "company interest" rating anywhere in the schema -- inventing scores
for them would be exactly the "fabricated precision" CLAUDE.md warns against
(see ``readiness.py``'s identical reasoning for uniform skill importance).
Add them here, as new components with a real weight, once that data exists.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApplicationPriorityWeights(BaseModel):
    """Configurable weights combining the three priority components into one score.

    Sums to 1.0 so the combined score stays in [0, 1].
    """

    model_config = ConfigDict(frozen=True)

    role_fit: float = Field(ge=0.0, le=1.0, default=0.4)
    readiness: float = Field(ge=0.0, le=1.0, default=0.4)
    user_preference: float = Field(ge=0.0, le=1.0, default=0.2)


DEFAULT_WEIGHTS = ApplicationPriorityWeights()


class ApplicationPriorityComponents(BaseModel):
    """The per-component breakdown behind one application's priority score."""

    model_config = ConfigDict(frozen=True)

    role_fit: float = Field(ge=0.0, le=1.0)
    readiness: float = Field(ge=0.0, le=1.0)
    user_preference: float = Field(ge=0.0, le=1.0)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def compute_role_fit(fit_score: float) -> float:
    """Clamp a ranker's raw similarity score into [0, 1].

    Embedding cosine similarity can be negative for unrelated text; TF-IDF
    cannot, but is clamped identically for a uniform component range.
    """
    return _clamp(fit_score)


def compute_preference_match(*, has_preference: bool, matched: bool) -> float:
    """One preference dimension's (role or location) contribution.

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


def score_application(
    components: ApplicationPriorityComponents, weights: ApplicationPriorityWeights = DEFAULT_WEIGHTS
) -> float:
    """Combine one application's components into a single explainable priority score."""
    raw = (
        weights.role_fit * components.role_fit
        + weights.readiness * components.readiness
        + weights.user_preference * components.user_preference
    )
    return _clamp(raw)
