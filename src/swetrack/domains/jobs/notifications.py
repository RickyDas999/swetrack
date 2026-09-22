"""Deciding which newly-discovered jobs deserve a local notification.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 13: "Notify only for a
newly discovered eligible job above a configurable priority threshold...
Quiet hours and per-company cooldowns prevent spam." Per-company cooldowns
are deferred (no measured spam problem at this project's job volume yet);
a priority threshold and quiet hours are implemented.

Dedup is a single ``DiscoveredJobRecord.notified_at`` timestamp, set only
once a notification is actually sent -- a job that doesn't clear the bar,
or arrives during quiet hours, is left un-notified and re-checked on the
next call rather than notified late or never.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from sqlalchemy.orm import Session

from swetrack.domains.applications.priority import compute_application_priority
from swetrack.domains.applications.services import list_applications
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.services import to_job_record
from swetrack.domains.opportunities.config import load_candidate_profile
from swetrack.domains.opportunities.models import CandidateProfile
from swetrack.domains.opportunities.ranking.base import Ranker
from swetrack.infrastructure.notifications.macos import send_macos_notification

DEFAULT_PRIORITY_THRESHOLD = 0.6


@dataclass(frozen=True)
class QuietHours:
    """A local-wall-clock window (may wrap past midnight) during which nothing is sent."""

    start_hour: int = 22
    end_hour: int = 8

    def contains(self, moment: datetime) -> bool:
        current = moment.time()
        start = time(hour=self.start_hour)
        end = time(hour=self.end_hour)
        if start <= end:
            return start <= current < end
        return current >= start or current < end


def notify_new_discoveries(
    session: Session,
    *,
    ranker: Ranker,
    profile: CandidateProfile | None = None,
    threshold: float = DEFAULT_PRIORITY_THRESHOLD,
    quiet_hours: QuietHours | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Notify for every un-notified, non-duplicate discovered job clearing the priority threshold.

    Returns the ``canonical_key`` of every job actually notified. ``now`` is
    local wall-clock time (quiet hours are a human concept), overridable for
    deterministic tests.
    """
    now = now or datetime.now()
    if quiet_hours is not None and quiet_hours.contains(now):
        return []

    profile = profile or load_candidate_profile()
    candidates = (
        session.query(DiscoveredJobRecord)
        .filter(DiscoveredJobRecord.notified_at.is_(None))
        .filter(DiscoveredJobRecord.duplicate_of_id.is_(None))
        .all()
    )

    notified: list[str] = []
    for record in candidates:
        applications = list_applications(session, job_id=record.canonical_key)
        if not applications:
            continue

        job = to_job_record(record)
        priority = compute_application_priority(
            session, application=applications[0], job=job, profile=profile, ranker=ranker
        )
        if priority.score < threshold:
            continue

        sent = send_macos_notification(
            title=f"New job match: {record.company_name}",
            subtitle=record.title,
            message=f"Priority {priority.score:.0%} -- {record.location_text or 'location unspecified'}",
        )
        if sent:
            record.notified_at = now
            session.commit()
            notified.append(record.canonical_key)

    return notified
