"""Job inbox: discovered jobs enriched with eligibility, discovery timing, and priority.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 13's dashboard inbox and
Section 14's list/filter API surface. Every entry keeps `source_published_at`
("published") and `first_seen_at` ("first found") as two separate fields,
never collapsed into one date -- Section 8: "source_updated_at must not be
presented as a publish date," and Checkpoint 4's acceptance criterion that
the dashboard keep these visually distinct.

ponytail: priority is recomputed per entry on every list call (TF-IDF
vectorization + BKT mastery lookups per job) rather than cached -- fine at
this project's scale (a personal job search, dozens of discovered jobs, not
a production job board); cache/paginate if the discovered_jobs table ever
grows into the thousands.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

from sqlalchemy.orm import Session

from swetrack.domains.applications.priority import ApplicationPriority, compute_application_priority
from swetrack.domains.applications.schemas import ApplicationStatus
from swetrack.domains.applications.services import list_applications
from swetrack.domains.jobs.candidate_config import load_candidate_eligibility_profile
from swetrack.domains.jobs.eligibility import EligibilityAssessment, EligibilityStatus, classify_new_grad_eligibility
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.normalize import ensure_utc
from swetrack.domains.jobs.schemas import CandidateEligibilityProfile
from swetrack.domains.jobs.services import to_job_record
from swetrack.domains.opportunities.config import load_candidate_profile
from swetrack.domains.opportunities.models import CandidateProfile
from swetrack.domains.opportunities.ranking.base import Ranker

_RECENT_HOURS = 24.0


class InboxEntry(BaseModel):
    """One discovered job, enriched for the job inbox view."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    company: str
    title: str
    location: str
    application_url: str
    source_type: str
    source_published_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    application_id: str | None
    application_status: ApplicationStatus | None
    eligibility: EligibilityAssessment
    priority: ApplicationPriority | None


def list_inbox(
    session: Session,
    *,
    ranker: Ranker,
    profile: CandidateProfile | None = None,
    candidate_eligibility: CandidateEligibilityProfile | None = None,
    eligibility_status: EligibilityStatus | None = None,
    application_status: ApplicationStatus | None = None,
    min_priority: float | None = None,
    since_hours: float | None = None,
) -> list[InboxEntry]:
    """Every non-duplicate discovered job, enriched and optionally filtered.

    Default order: eligible-and-first-seen-in-the-last-24h first, then
    priority descending, then first-seen descending -- CLAUDE.md's dashboard
    inbox default sort order.
    """
    profile = profile or load_candidate_profile()
    candidate_eligibility = candidate_eligibility or load_candidate_eligibility_profile()
    now = datetime.now(timezone.utc)

    records = session.query(DiscoveredJobRecord).filter(DiscoveredJobRecord.duplicate_of_id.is_(None)).all()

    entries: list[InboxEntry] = []
    for record in records:
        first_seen_at = ensure_utc(record.first_seen_at)
        if since_hours is not None and (now - first_seen_at).total_seconds() / 3600.0 > since_hours:
            continue

        assessment = classify_new_grad_eligibility(
            title=record.title, description=record.description_plain, candidate=candidate_eligibility
        )
        if eligibility_status is not None and assessment.status != eligibility_status:
            continue

        applications = list_applications(session, job_id=record.canonical_key)
        application = applications[0] if applications else None
        if application_status is not None and (application is None or application.status != application_status):
            continue

        priority: ApplicationPriority | None = None
        if application is not None:
            priority = compute_application_priority(
                session,
                application=application,
                job=to_job_record(record),
                profile=profile,
                ranker=ranker,
                candidate_eligibility=candidate_eligibility,
            )
        if min_priority is not None and (priority is None or priority.score < min_priority):
            continue

        entries.append(
            InboxEntry(
                job_id=record.canonical_key,
                company=record.company_name,
                title=record.title,
                location=record.location_text,
                application_url=record.application_url,
                source_type=record.source_type,
                source_published_at=ensure_utc(record.source_published_at),
                first_seen_at=first_seen_at,
                last_seen_at=ensure_utc(record.last_seen_at),
                application_id=application.id if application else None,
                application_status=application.status if application else None,
                eligibility=assessment,
                priority=priority,
            )
        )

    entries.sort(key=lambda entry: _sort_key(entry, now))
    return entries


def _sort_key(entry: InboxEntry, now: datetime) -> tuple[bool, float, float]:
    recently_seen_eligible = entry.eligibility.status == "eligible" and (
        (now - entry.first_seen_at).total_seconds() / 3600.0 <= _RECENT_HOURS
    )
    priority_score = entry.priority.score if entry.priority is not None else 0.0
    return (not recently_seen_eligible, -priority_score, -entry.first_seen_at.timestamp())
