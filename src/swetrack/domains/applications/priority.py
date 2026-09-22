"""Application Priority: connects Role Fit, Readiness, freshness, eligibility,
preference, comp, and deadline for one application.

CLAUDE.md Phase 14. Deliberately reuses ``opportunities.readiness.compute_readiness``
rather than recomputing Fit/Readiness -- Application Priority is a re-weighted
combination of those two existing, independently-computed scores plus
freshness/eligibility/preference/company/compensation/deadline components,
never a replacement for either. Each component stays visible on the result;
CLAUDE.md: "Do not create one mysterious ML-generated number."

Job Radar Checkpoint 3 adds ``freshness`` (0 for a job never run through
discovery -- e.g. every sample/CSV job) and ``new_grad_confidence`` (from the
deterministic eligibility classifier, inverted for a confidently-ineligible
job so a "definitely senior" posting scores low here, not high).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from swetrack.domains.applications.schemas import Application, ApplicationStatus
from swetrack.domains.jobs.candidate_config import load_candidate_eligibility_profile
from swetrack.domains.jobs.eligibility import EligibilityAssessment, classify_new_grad_eligibility
from swetrack.domains.jobs.freshness import compute_freshness
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.schemas import CandidateEligibilityProfile
from swetrack.domains.opportunities.models import CandidateProfile, JobRecord
from swetrack.domains.opportunities.ranking.base import Ranker, build_match_reasons
from swetrack.domains.opportunities.readiness import ReadinessResult, compute_readiness
from swetrack.ml.application_priority.ranker import (
    DEFAULT_WEIGHTS,
    PRIORITY_VERSION,
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
    version: str = PRIORITY_VERSION


def _freshness_for_job(session: Session, job: JobRecord) -> float:
    """0.0 for a job never run through Job Radar discovery (every sample/CSV job today)."""
    record = session.query(DiscoveredJobRecord).filter(DiscoveredJobRecord.canonical_key == job.job_id).one_or_none()
    if record is None:
        return 0.0
    return compute_freshness(source_published_at=record.source_published_at, first_seen_at=record.first_seen_at)


def _new_grad_confidence_for_job(job: JobRecord, candidate: CandidateEligibilityProfile) -> float:
    """The eligibility classifier's confidence, inverted when the job is confidently ineligible.

    "eligible"/"uncertain" use the raw confidence directly (higher = more
    priority-worthy); "ineligible" inverts it so a confidently senior/intern
    posting scores LOW here rather than high (a high confidence score is not
    itself a reason to prioritize a job the classifier just excluded).
    """
    assessment: EligibilityAssessment = classify_new_grad_eligibility(
        title=job.title, description=job.description, candidate=candidate
    )
    if assessment.status == "ineligible":
        return 1.0 - assessment.confidence
    return assessment.confidence


def compute_application_priority(
    session: Session,
    *,
    application: Application,
    job: JobRecord,
    profile: CandidateProfile,
    ranker: Ranker,
    weights: ApplicationPriorityWeights = DEFAULT_WEIGHTS,
    candidate_eligibility: CandidateEligibilityProfile | None = None,
    today: date | None = None,
) -> ApplicationPriority:
    """Compute one application's priority against its job, the candidate profile, and tracked mastery.

    ``candidate_eligibility`` defaults to the checked-in example profile
    (``load_candidate_eligibility_profile()``) when not supplied -- this is
    a single-user, no-auth local app (CLAUDE.md), so there is no per-request
    alternative, matching how ``GET /opportunities/{id}/readiness`` already
    treats the example ``CandidateProfile``.

    ``today`` defaults to the real current date; overridable for deterministic
    tests of ``deadline_urgency``.
    """
    today = today or date.today()
    candidate_eligibility = candidate_eligibility or load_candidate_eligibility_profile()
    readiness_result = compute_readiness(session, job=job, profile=profile, ranker=ranker)
    match_reasons = build_match_reasons(profile, job)

    days_until_deadline = (job.application_deadline - today).days if job.application_deadline else None

    components = ApplicationPriorityComponents(
        role_fit=compute_role_fit(readiness_result.fit_score),
        readiness=readiness_result.readiness_score,
        freshness=_freshness_for_job(session, job),
        new_grad_confidence=_new_grad_confidence_for_job(job, candidate_eligibility),
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


def rank_application_priorities(
    session: Session,
    *,
    applications: list[Application],
    jobs_by_id: dict[str, JobRecord],
    profile: CandidateProfile,
    ranker: Ranker,
    weights: ApplicationPriorityWeights = DEFAULT_WEIGHTS,
    candidate_eligibility: CandidateEligibilityProfile | None = None,
    today: date | None = None,
) -> list[ApplicationPriority]:
    """Compute priority for a batch of applications, sorted highest score first.

    ``jobs_by_id`` is loaded once by the caller (rather than re-reading the
    jobs CSV per application) since this can be called over many tracked
    applications at once -- the "Top Opportunities" list from CLAUDE.md's
    product end-state. An application whose ``job_id`` is no longer present
    in ``jobs_by_id`` (the seed data changed since it was created) is
    silently skipped rather than erroring the whole batch.
    """
    candidate_eligibility = candidate_eligibility or load_candidate_eligibility_profile()
    results = [
        compute_application_priority(
            session,
            application=application,
            job=job,
            profile=profile,
            ranker=ranker,
            weights=weights,
            candidate_eligibility=candidate_eligibility,
            today=today,
        )
        for application in applications
        if (job := jobs_by_id.get(application.job_id)) is not None
    ]
    results.sort(key=lambda result: (-result.score, result.application_id))
    return results
