"""Application Priority: connects Role Fit, Readiness, preference, comp, and deadline for one application.

CLAUDE.md Phase 14. Deliberately reuses ``opportunities.readiness.compute_readiness``
rather than recomputing Fit/Readiness -- Application Priority is a re-weighted
combination of those two existing, independently-computed scores plus
preference/company/compensation/deadline components, never a replacement for
either. Each component stays visible on the result; CLAUDE.md: "Do not
create one mysterious ML-generated number."
"""

from __future__ import annotations

from datetime import date

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
    compute_compensation_fit,
    compute_deadline_urgency,
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
    today: date | None = None,
) -> ApplicationPriority:
    """Compute one application's priority against its job, the candidate profile, and tracked mastery.

    ``today`` defaults to the real current date; overridable for deterministic
    tests of ``deadline_urgency``.
    """
    today = today or date.today()
    readiness_result = compute_readiness(session, job=job, profile=profile, ranker=ranker)
    match_reasons = build_match_reasons(profile, job)

    days_until_deadline = (job.application_deadline - today).days if job.application_deadline else None

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
        company_interest=compute_preference_match(
            has_preference=bool(profile.preferred_companies), matched=bool(match_reasons.matched_companies)
        ),
        compensation_fit=compute_compensation_fit(
            job_compensation_max=job.compensation_max, candidate_minimum=profile.minimum_compensation
        ),
        deadline_urgency=compute_deadline_urgency(days_until_deadline),
    )

    return ApplicationPriority(
        application_id=application.id,
        job_id=job.job_id,
        status=application.status,
        score=score_application(components, weights),
        components=components,
        readiness=readiness_result,
    )
