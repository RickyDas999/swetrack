"""Freshness scoring: how recently a job was published or first discovered.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 10's monotonic decay
table. Prefers ``source_published_at`` when a source trustworthily exposes
it; falls back to ``first_seen_at`` ("first found") otherwise -- Section 8:
"source_updated_at must not be presented as a publish date."
"""

from __future__ import annotations

from datetime import datetime, timezone

from swetrack.domains.jobs.normalize import ensure_utc

FRESHNESS_VERSION = "freshness-v1"

# (max_age_hours, score_0_to_100), checked in order; anything older than the
# last bucket falls through to _STALE_SCORE.
_DECAY_TABLE: list[tuple[float, float]] = [
    (2, 100.0),
    (6, 90.0),
    (12, 80.0),
    (24, 65.0),
    (24 * 3, 45.0),
    (24 * 7, 25.0),
]
_STALE_SCORE = 10.0


def compute_freshness(
    *,
    source_published_at: datetime | None,
    first_seen_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """A [0, 1] freshness score (the handoff's 0-100 scale, divided by 100 for
    consistency with every other ApplicationPriorityComponents field).

    Returns 0.0 when neither timestamp is known -- nothing to compute a
    freshness signal from (e.g. a sample/CSV job that was never discovered
    through Job Radar).
    """
    reference = ensure_utc(source_published_at) or ensure_utc(first_seen_at)
    if reference is None:
        return 0.0

    now = ensure_utc(now) if now is not None else datetime.now(timezone.utc)
    age_hours = max(0.0, (now - reference).total_seconds() / 3600.0)

    for max_age_hours, score in _DECAY_TABLE:
        if age_hours <= max_age_hours:
            return score / 100.0
    return _STALE_SCORE / 100.0
