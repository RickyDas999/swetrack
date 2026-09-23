"""CLI: import the public discovery feed into the local, private database.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 5: "The local app imports
that feed and performs personalized scoring privately." Reuses the exact
same sync_source path the ATS adapters use (Checkpoint 2), so it's
idempotent for the same reason: re-running never duplicates a job, and a
newly-imported non-duplicate job auto-creates a "discovered" application
that flows through the existing Application Priority pipeline.

    python scripts/import_public_feed.py
    python scripts/import_public_feed.py --feed public/latest_jobs.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from swetrack.domains.jobs.public_feed import PublicFeed
from swetrack.domains.jobs.schemas import NormalizedJob
from swetrack.domains.jobs.services import sync_source
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_FEED_PATH = find_repo_root() / "public" / "latest_jobs.json"


def _to_normalized_job(entry) -> NormalizedJob:
    return NormalizedJob(
        source_type=entry.source_type,
        source_job_id=entry.source_job_id,
        company_name=entry.company_name,
        title=entry.title,
        location_text=entry.location_text,
        description_plain=entry.description_plain,
        application_url=entry.application_url,
        source_url=entry.source_url,
        source_published_at=entry.source_published_at,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feed", type=Path, default=DEFAULT_FEED_PATH)
    args = parser.parse_args()

    if not args.feed.exists():
        raise SystemExit(f"Feed file not found: {args.feed} -- run scripts/public_discovery.py first, or `git pull`.")

    feed = PublicFeed.model_validate_json(args.feed.read_text(encoding="utf-8"))
    jobs = [_to_normalized_job(entry) for entry in feed.jobs]

    engine = get_engine()
    init_db(engine)
    session = get_sessionmaker(engine)()
    try:
        result = sync_source(session, source_type="public-feed", jobs=jobs)
    finally:
        session.close()

    print(
        f"Imported {result.total_fetched} job(s) from {args.feed} "
        f"(new={result.new_count} updated={result.updated_count} "
        f"unchanged={result.unchanged_count} duplicate={result.duplicate_count})"
    )


if __name__ == "__main__":
    main()
