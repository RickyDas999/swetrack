"""The only write path to discovered_jobs (idempotent upsert, revision
handling, cross-source duplicate flagging, application auto-creation), plus
the read-side conversion into the shape the existing ranking/readiness/
priority pipeline already consumes.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 8 (normalization/dedup)
and Checkpoint 2 (persistence). A newly-discovered, non-duplicate job
auto-creates a "discovered"-status ``ApplicationRecord`` immediately
(docs/job-radar-integration-plan.md Section 8's decided design) so it flows
through the existing Application Priority pipeline unchanged -- no second,
parallel job-level scoring path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from swetrack.domains.applications.services import create_application
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.jobs.normalize import cross_source_key, strip_tracking_params
from swetrack.domains.jobs.schemas import NormalizedJob, SyncResult
from swetrack.domains.opportunities.models import JobRecord

logger = logging.getLogger(__name__)

# A ratio, not an exact match, so minor whitespace/formatting differences
# between the same JD mirrored across two ATS platforms don't defeat dedup.
_DESCRIPTION_SIMILARITY_THRESHOLD = 0.9


def sync_source(session: Session, *, source_type: str, jobs: list[NormalizedJob]) -> SyncResult:
    """Upsert every job from one source's fetch() result. Idempotent: safe to call repeatedly."""
    counts = {"new": 0, "updated": 0, "unchanged": 0, "duplicate": 0}

    for job in jobs:
        canonical_key = f"{job.source_type}:{job.source_job_id}"
        existing = (
            session.query(DiscoveredJobRecord).filter(DiscoveredJobRecord.canonical_key == canonical_key).one_or_none()
        )

        if existing is not None:
            changed = _fields_changed(existing, job)
            _apply_mutable_fields(existing, job)
            # Bump explicitly rather than relying on the column's `onupdate`:
            # a re-sync with no field changes should still record "seen
            # again now" for freshness, and onupdate only fires when
            # SQLAlchemy's flush actually issues an UPDATE.
            existing.last_seen_at = datetime.now(timezone.utc)
            session.commit()
            counts["updated" if changed else "unchanged"] += 1
            logger.info(
                "job.%s", "revision" if changed else "reseen", extra={"canonical_key": canonical_key}
            )
            continue

        duplicate_of = _find_cross_source_duplicate(session, job)
        record = DiscoveredJobRecord(
            canonical_key=canonical_key,
            source_type=job.source_type,
            source_job_id=job.source_job_id,
            duplicate_of_id=duplicate_of.id if duplicate_of is not None else None,
        )
        _apply_mutable_fields(record, job)
        session.add(record)
        session.commit()

        if duplicate_of is not None:
            counts["duplicate"] += 1
            logger.info(
                "job.duplicate", extra={"canonical_key": canonical_key, "duplicate_of": duplicate_of.canonical_key}
            )
        else:
            counts["new"] += 1
            logger.info("job.new", extra={"canonical_key": canonical_key})
            # Only the primary (non-duplicate) row gets a tracked
            # application -- a flagged duplicate represents the same
            # real-world job as an already-tracked row, and a second
            # application would split one job's signal across two Priority
            # scores.
            create_application(session, job_id=canonical_key, status="discovered")

    return SyncResult(
        source_type=source_type,
        total_fetched=len(jobs),
        new_count=counts["new"],
        updated_count=counts["updated"],
        unchanged_count=counts["unchanged"],
        duplicate_count=counts["duplicate"],
    )


def _apply_mutable_fields(record: DiscoveredJobRecord, job: NormalizedJob) -> None:
    """Copy every field that can legitimately change between syncs onto `record`.

    Deliberately excludes ``first_seen_at``, ``closed_at``, and
    ``duplicate_of_id`` -- provenance and duplicate linkage never move once
    set.
    """
    record.company_name = job.company_name
    record.title = job.title
    record.location_text = job.location_text
    record.workplace_type = job.workplace_type
    record.employment_type = job.employment_type
    record.description_plain = job.description_plain
    record.application_url = job.application_url
    record.source_url = job.source_url
    record.source_published_at = job.source_published_at
    record.source_updated_at = job.source_updated_at


def _fields_changed(record: DiscoveredJobRecord, job: NormalizedJob) -> bool:
    """Whether this re-sync represents a real content revision, for logging/metrics only."""
    return (
        record.title != job.title
        or record.description_plain != job.description_plain
        or record.location_text != job.location_text
        or record.application_url != job.application_url
    )


def _find_cross_source_duplicate(session: Session, job: NormalizedJob) -> DiscoveredJobRecord | None:
    """A different-source row that is probably the same real job.

    SWETrack_Job_Radar_Claude_Code_Handoff.md Section 8, rules 4-5: same
    normalized company+title+location, AND either the same
    (tracking-param-stripped) URL or a near-identical description.

    ponytail: scans every existing row and normalizes in Python rather than
    querying an indexed normalized-key column -- fine at this project's
    scale (a personal job search, not a production job board); add
    normalized/indexed columns if a sync ever needs to scan thousands of
    rows.
    """
    target_key = cross_source_key(job.company_name, job.title, job.location_text)
    target_url = strip_tracking_params(job.application_url)

    candidates = session.query(DiscoveredJobRecord).filter(DiscoveredJobRecord.source_type != job.source_type)
    for candidate in candidates:
        if cross_source_key(candidate.company_name, candidate.title, candidate.location_text) != target_key:
            continue
        same_url = bool(target_url) and strip_tracking_params(candidate.application_url) == target_url
        same_description = _descriptions_match(candidate.description_plain, job.description_plain)
        if same_url or same_description:
            return candidate
    return None


def _descriptions_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= _DESCRIPTION_SIMILARITY_THRESHOLD


def to_job_record(record: DiscoveredJobRecord) -> JobRecord:
    """Convert a persisted discovered job into the shape ranking/readiness/priority already consume.

    ``JobRecord`` (opportunities.models) is the one shape ``Ranker.score_jobs``,
    ``compute_readiness``, and ``compute_application_priority`` already
    accept -- docs/job-radar-integration-plan.md Section 7. ``job_id`` is
    the ``canonical_key``, matching what ``ApplicationRecord.job_id`` stores
    for jobs discovered this way (Section 6).

    ``skills=[]``: Job Radar does not extract structured skills from JD text
    yet, so Role Fit still works (it also scores the free-text
    title/description), but Readiness for a discovered job is currently a
    placeholder ``1.0`` ("nothing to be unprepared for") until a future
    checkpoint adds skill extraction -- see the Checkpoint 3 summary's Known
    Limitations, not a claim that a discovered job has no skill
    requirements.
    """
    return JobRecord(
        job_id=record.canonical_key,
        company=record.company_name,
        title=record.title,
        location=record.location_text,
        description=record.description_plain,
        skills=[],
        experience_level="",
        url=record.application_url,
        source="discovered",
    )


def list_discovered_job_records(session: Session, *, include_duplicates: bool = False) -> list[JobRecord]:
    """Every persisted discovered job as a JobRecord, ready for the existing ranking pipeline.

    Excludes cross-source duplicates by default: a duplicate row does not
    get its own tracked application (see sync_source), so it is not a
    distinct actionable item for a caller like the job listing/ranking
    endpoints.
    """
    query = session.query(DiscoveredJobRecord)
    if not include_duplicates:
        query = query.filter(DiscoveredJobRecord.duplicate_of_id.is_(None))
    return [to_job_record(record) for record in query.all()]
