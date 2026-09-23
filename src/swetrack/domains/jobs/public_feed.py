"""Public-data-only job feed: what the optional GitHub Actions discovery plane produces.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 5 (always-on discovery
plane) / Checkpoint 7. Structurally cannot leak private data: this module
never imports ``infrastructure.database`` (no SQLite session, ever), never
reads ``resume/master_resume.tex`` or ``config/candidate.example.yaml``
(the named candidate identity), and every field on ``PublicFeedEntry`` is
already-public ATS data. Personalized scoring (the real candidate profile,
Role Fit, Readiness, Application Priority) happens only locally, after
``scripts/import_public_feed.py`` hands entries to the existing
``sync_source`` pipeline.

Eligibility here uses a *generic* candidate (no name, current calendar year
as the graduation-year signal) purely to filter obviously-irrelevant
postings (confidently senior/intern roles) out of the public feed and keep
it small -- it is not a personalized result. The local importer's own
pipeline re-classifies with the real candidate profile.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from swetrack.domains.jobs.eligibility import EligibilityStatus, classify_new_grad_eligibility
from swetrack.domains.jobs.normalize import cross_source_key, ensure_utc, strip_tracking_params
from swetrack.domains.jobs.schemas import CandidateEligibilityProfile, NormalizedJob, SourceType

PUBLIC_FEED_VERSION = "public-feed-v1"

DEFAULT_MAX_AGE_DAYS = 14.0
DEFAULT_MAX_ENTRIES = 500

# Forbidden substrings a generated feed must never contain -- defense in
# depth on top of this module's structural guarantee (it never reads
# private files at all). See tests/test_public_feed.py and the
# secret-scan step in .github/workflows/public-discovery.yml.
FORBIDDEN_MARKERS = ("master_resume", "evidence.yaml", "swetrack.db", "candidate.example.yaml")


class PublicFeedEntry(BaseModel):
    """One job in the public feed. Every field is already-public ATS data."""

    model_config = ConfigDict(frozen=True)

    canonical_key: str
    source_type: SourceType
    source_job_id: str
    company_name: str
    title: str
    location_text: str = ""
    description_plain: str = ""
    application_url: str = ""
    source_url: str = ""
    source_published_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    eligibility_status: EligibilityStatus
    eligibility_confidence: float = Field(ge=0.0, le=1.0)


class PublicFeed(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = PUBLIC_FEED_VERSION
    generated_at: datetime
    jobs: list[PublicFeedEntry]


def generic_candidate(*, year: int | None = None) -> CandidateEligibilityProfile:
    """A non-identifying candidate profile for the public pass's eligibility filter.

    No name, no school -- just the current calendar year (a reasonable
    generic "new grad this cycle" default) and the classifier's own default
    excluded levels.
    """
    return CandidateEligibilityProfile(
        name="Generic Candidate",
        graduation_year=year or datetime.now(timezone.utc).year,
    )


def to_public_feed_entry(job: NormalizedJob, *, candidate: CandidateEligibilityProfile, now: datetime) -> PublicFeedEntry | None:
    """Classify one job and return its feed entry, or None if it's confidently ineligible."""
    assessment = classify_new_grad_eligibility(title=job.title, description=job.description_plain, candidate=candidate)
    if assessment.status == "ineligible":
        return None

    return PublicFeedEntry(
        canonical_key=f"{job.source_type}:{job.source_job_id}",
        source_type=job.source_type,
        source_job_id=job.source_job_id,
        company_name=job.company_name,
        title=job.title,
        location_text=job.location_text,
        description_plain=job.description_plain,
        application_url=job.application_url,
        source_url=job.source_url,
        source_published_at=job.source_published_at,
        first_seen_at=now,
        last_seen_at=now,
        eligibility_status=assessment.status,
        eligibility_confidence=assessment.confidence,
    )


def merge_feed_entries(
    previous: list[PublicFeedEntry], fresh: list[PublicFeedEntry], *, now: datetime
) -> list[PublicFeedEntry]:
    """Combine a freshly-fetched batch with the existing feed.

    A job already in ``previous`` keeps its original ``first_seen_at`` and
    gets ``last_seen_at`` bumped to ``now`` plus its freshly re-classified
    fields (a description/eligibility re-check); a genuinely new job is
    added with both timestamps set to ``now``. A previously-seen job that
    didn't reappear in this fetch is left untouched here -- retention
    (``apply_retention``) is what eventually drops stale entries, not a
    single missing fetch.
    """
    by_key = {entry.canonical_key: entry for entry in previous}
    fresh_by_key = {entry.canonical_key: entry for entry in fresh}

    merged: dict[str, PublicFeedEntry] = dict(by_key)
    for key, fresh_entry in fresh_by_key.items():
        existing = by_key.get(key)
        first_seen_at = ensure_utc(existing.first_seen_at) if existing is not None else now
        merged[key] = fresh_entry.model_copy(update={"first_seen_at": first_seen_at, "last_seen_at": now})

    return list(merged.values())


def _cross_source_duplicate_keys(entries: list[PublicFeedEntry]) -> set[str]:
    """canonical_keys of entries that are a probable cross-source duplicate of an earlier one.

    Same simplified rule as domains/jobs/services.py: same normalized
    company+title+location and a matching (tracking-param-stripped) URL --
    flagged, not merged, and always keeping the earliest-seen copy.
    """
    seen_group_keys: dict[str, str] = {}  # cross_source_key -> canonical_key of the one we keep
    duplicates: set[str] = set()
    for entry in sorted(entries, key=lambda e: ensure_utc(e.first_seen_at)):
        group_key = cross_source_key(entry.company_name, entry.title, entry.location_text)
        stripped_url = strip_tracking_params(entry.application_url)
        existing_canonical_key = seen_group_keys.get(group_key)
        if existing_canonical_key is None:
            seen_group_keys[group_key] = entry.canonical_key
            continue
        existing_entry = next(e for e in entries if e.canonical_key == existing_canonical_key)
        if stripped_url and strip_tracking_params(existing_entry.application_url) == stripped_url:
            duplicates.add(entry.canonical_key)
    return duplicates


def apply_retention(
    entries: list[PublicFeedEntry],
    *,
    now: datetime,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> list[PublicFeedEntry]:
    """Drop stale entries and cap total size, keeping the freshest-first-seen jobs.

    Also drops cross-source duplicates (keeping the earliest-seen copy) --
    this is what keeps a compact public feed "compact" over time.
    """
    duplicate_keys = _cross_source_duplicate_keys(entries)
    kept = [
        entry
        for entry in entries
        if entry.canonical_key not in duplicate_keys
        and (now - ensure_utc(entry.first_seen_at)).total_seconds() / 86400.0 <= max_age_days
    ]
    kept.sort(key=lambda entry: ensure_utc(entry.first_seen_at), reverse=True)
    return kept[:max_entries]


def contains_forbidden_content(text: str) -> list[str]:
    """Which forbidden markers (if any) appear in `text`. Empty list means the scan passed."""
    lowered = text.lower()
    return [marker for marker in FORBIDDEN_MARKERS if marker.lower() in lowered]
