"""Application Priority: connects Role Fit, Readiness, and preference match for one application.

CLAUDE.md Phase 14. Deliberately reuses ``opportunities.readiness.compute_readiness``
rather than recomputing Fit/Readiness -- Application Priority is a re-weighted
combination of those two existing, independently-computed scores plus one new
preference-match component, never a replacement for either. Each component
stays visible on the result; CLAUDE.md: "Do not create one mysterious
ML-generated number."
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from swetrack.domains.applications.schemas import Application, ApplicationStatus
from swetrack.domains.opportunities.models import CandidateProfile, JobRecord
from swetrack.domains.opportunities.ranking.base import Ranker, build_match_reasons
from swetrack.domains.opportunities.readiness import ReadinessResult, compute_readiness
from swetrack.ml.application_priority.ranker import (
    DEFAULT_WEIGHTS,
    ApplicationPriorityComponents,
    ApplicationPriorityWeights,
    compute_preference_match,
    compute_role_fit,
    compute_user_preference,
    score_application,
)


class ApplicationPriority(BaseModel):
    """One application's explainable priority score, with the Readiness it was derived from."""

    model_config = ConfigDict(frozen=True)

    application_id: str
    job_id: str
    status: ApplicationStatus
    score: float = Field(ge=0.0, le=1.0)
    components: ApplicationPriorityComponents
    readiness: ReadinessResult


def compute_application_priority(
    session: Session,
    *,
    application: Application,
    job: JobRecord,
    profile: CandidateProfile,
    ranker: Ranker,
    weights: ApplicationPriorityWeights = DEFAULT_WEIGHTS,
) -> ApplicationPriority:
    """Compute one application's priority against its job, the candidate profile, and tracked mastery."""
    readiness_result = compute_readiness(session, job=job, profile=profile, ranker=ranker)
    match_reasons = build_match_reasons(profile, job)

    components = ApplicationPriorityComponents(
        role_fit=compute_role_fit(readiness_result.fit_score),
        readiness=readiness_result.readiness_score,
        user_preference=compute_user_preference(
            role_preference_match=compute_preference_match(
                has_preference=bool(profile.preferred_roles), matched=bool(match_reasons.matched_roles)
            ),
            location_preference_match=compute_preference_match(
                has_preference=bool(profile.preferred_locations), matched=bool(match_reasons.matched_locations)
            ),
        ),
    )

    return ApplicationPriority(
        application_id=application.id,
        job_id=job.job_id,
        status=application.status,
        score=score_application(components, weights),
        components=components,
        readiness=readiness_result,
    )
