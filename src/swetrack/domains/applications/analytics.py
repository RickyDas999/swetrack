"""Outcome analytics: funnel, time-to-apply, source yield, and response rate.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 20 / Checkpoint 8.
Descriptive statistics over your own tracked history only -- every function
here reports counts/medians from ``ApplicationStatusEventRecord``'s
immutable history, never a model, never a claim of causation ("applying
faster CAUSES more interviews"), and never a comparison to other
candidates or a benchmark. A rate with too few observations to be
meaningful is reported as ``None`` with its sample size shown, rather than
a possibly-noisy percentage presented as if it were solid.

"Funnel" here is a job's *ever reached* a status (from history), not its
current status -- an application discovered -> applied -> rejected still
counts as having reached "applied." CLAUDE.md Phase 12 explicitly leaves
the status graph unconstrained (any status from any status), so a
current-status-only funnel would undercount real progress.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from swetrack.domains.applications.schemas import ApplicationStatus
from swetrack.domains.applications.services import get_application_history, list_applications
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.normalize import ensure_utc

ANALYTICS_CAVEAT = (
    "Descriptive statistics over your own tracked history only -- not causal, not a "
    "benchmark against other candidates, and small-sample rates can be noisy."
)

# Funnel progression order, per CLAUDE.md Phase 12's own status list.
# "rejected"/"withdrawn" are terminal outcomes, reported separately, not as
# funnel progress stages.
_FUNNEL_STAGES: tuple[ApplicationStatus, ...] = (
    "discovered",
    "interested",
    "applied",
    "oa",
    "recruiter_screen",
    "technical",
    "system_design",
    "behavioral",
    "final",
    "offer",
)
_RESPONSE_STAGES = {"oa", "recruiter_screen", "technical", "system_design", "behavioral", "final", "offer"}


class FunnelStage(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ApplicationStatus
    reached_count: int = Field(ge=0)


class FunnelReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_applications: int = Field(ge=0)
    stages: list[FunnelStage]
    rejected_count: int = Field(ge=0)
    withdrawn_count: int = Field(ge=0)


class TimeToApplyStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_size: int = Field(ge=0)
    median_hours: float | None = None
    mean_hours: float | None = None


class SourceYield(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: str
    discovered_count: int = Field(ge=0)
    applications_count: int = Field(ge=0)
    interviewed_count: int = Field(ge=0)
    offer_count: int = Field(ge=0)


class ResponseRateStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    applied_count: int = Field(ge=0)
    responded_count: int = Field(ge=0)
    response_rate: float | None = None


class AnalyticsReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    funnel: FunnelReport
    time_to_apply: TimeToApplyStats
    source_yield: list[SourceYield]
    response_rate: ResponseRateStats
    caveat: str = ANALYTICS_CAVEAT


def _history_status_sets(session: Session, application_ids: list[str]) -> dict[str, set[str]]:
    """Every status each application has ever reached, in one pass."""
    return {app_id: {event.to_status for event in get_application_history(session, app_id)} for app_id in application_ids}


def compute_funnel(session: Session) -> FunnelReport:
    applications = list_applications(session)
    statuses_by_app = _history_status_sets(session, [app.id for app in applications])

    stages = [
        FunnelStage(status=stage, reached_count=sum(1 for statuses in statuses_by_app.values() if stage in statuses))
        for stage in _FUNNEL_STAGES
    ]
    rejected = sum(1 for statuses in statuses_by_app.values() if "rejected" in statuses)
    withdrawn = sum(1 for statuses in statuses_by_app.values() if "withdrawn" in statuses)

    return FunnelReport(total_applications=len(applications), stages=stages, rejected_count=rejected, withdrawn_count=withdrawn)


def compute_time_to_apply(session: Session) -> TimeToApplyStats:
    applications = list_applications(session)
    durations_hours: list[float] = []
    for app in applications:
        history = get_application_history(session, app.id)
        applied_events = [event for event in history if event.to_status == "applied"]
        if not applied_events:
            continue
        first_applied = min(applied_events, key=lambda event: event.timestamp)
        delta = ensure_utc(first_applied.timestamp) - ensure_utc(app.created_at)
        durations_hours.append(max(0.0, delta.total_seconds() / 3600.0))

    if not durations_hours:
        return TimeToApplyStats(sample_size=0)
    return TimeToApplyStats(
        sample_size=len(durations_hours),
        median_hours=statistics.median(durations_hours),
        mean_hours=statistics.mean(durations_hours),
    )


def _source_type_for_job_id(job_id: str, discovered_by_key: dict[str, DiscoveredJobRecord]) -> str:
    record = discovered_by_key.get(job_id)
    return record.source_type if record is not None else "sample"


def compute_source_yield(session: Session) -> list[SourceYield]:
    applications = list_applications(session)
    discovered_by_key = {record.canonical_key: record for record in session.query(DiscoveredJobRecord).all()}
    statuses_by_app = _history_status_sets(session, [app.id for app in applications])

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"discovered": 0, "applications": 0, "interviewed": 0, "offers": 0})

    for record in discovered_by_key.values():
        if record.duplicate_of_id is None:
            counts[record.source_type]["discovered"] += 1

    for app in applications:
        source_type = _source_type_for_job_id(app.job_id, discovered_by_key)
        counts[source_type]["applications"] += 1
        statuses = statuses_by_app[app.id]
        if statuses & _RESPONSE_STAGES:
            counts[source_type]["interviewed"] += 1
        if "offer" in statuses:
            counts[source_type]["offers"] += 1

    return [
        SourceYield(
            source_type=source_type,
            discovered_count=c["discovered"],
            applications_count=c["applications"],
            interviewed_count=c["interviewed"],
            offer_count=c["offers"],
        )
        for source_type, c in sorted(counts.items())
    ]


def compute_response_rate(session: Session) -> ResponseRateStats:
    applications = list_applications(session)
    statuses_by_app = _history_status_sets(session, [app.id for app in applications])

    applied_count = 0
    responded_count = 0
    for statuses in statuses_by_app.values():
        if "applied" not in statuses:
            continue
        applied_count += 1
        if statuses & _RESPONSE_STAGES:
            responded_count += 1

    rate = (responded_count / applied_count) if applied_count > 0 else None
    return ResponseRateStats(applied_count=applied_count, responded_count=responded_count, response_rate=rate)


def compute_analytics_report(session: Session, *, now: datetime) -> AnalyticsReport:
    return AnalyticsReport(
        generated_at=now,
        funnel=compute_funnel(session),
        time_to_apply=compute_time_to_apply(session),
        source_yield=compute_source_yield(session),
        response_rate=compute_response_rate(session),
    )
