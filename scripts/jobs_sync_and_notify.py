"""CLI: sync every enabled registry source, then notify for newly-qualifying jobs.

This is the one command the LaunchAgent (install_launch_agent.py) runs
periodically. SWETrack_Job_Radar_Claude_Code_Handoff.md Section 13: "A
macOS LaunchAgent runs every 15 minutes while the computer is awake."
Uses TfidfRanker (not the embedding model) so a periodic background run
never triggers a model download.

    python scripts/jobs_sync_and_notify.py
    python scripts/jobs_sync_and_notify.py --threshold 0.7 --quiet-hours-start 23 --quiet-hours-end 7
"""

from __future__ import annotations

import argparse

from swetrack.domains.jobs.notifications import DEFAULT_PRIORITY_THRESHOLD, QuietHours, notify_new_discoveries
from swetrack.domains.jobs.registry import DEFAULT_SOURCES_PATH, build_adapter, load_source_registry
from swetrack.domains.jobs.services import sync_source
from swetrack.domains.opportunities.ranking.tfidf import TfidfRanker
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", default=str(DEFAULT_SOURCES_PATH))
    parser.add_argument("--threshold", type=float, default=DEFAULT_PRIORITY_THRESHOLD)
    parser.add_argument("--quiet-hours-start", type=int, default=22)
    parser.add_argument("--quiet-hours-end", type=int, default=8)
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)
    session = get_sessionmaker(engine)()
    try:
        entries = load_source_registry(args.registry)
        for entry in entries:
            if not entry.enabled:
                continue
            jobs = build_adapter(entry).fetch()
            result = sync_source(session, source_type=entry.adapter, jobs=jobs)
            print(
                f"{entry.company}: fetched={result.total_fetched} new={result.new_count} "
                f"updated={result.updated_count} duplicate={result.duplicate_count}"
            )

        quiet_hours = QuietHours(start_hour=args.quiet_hours_start, end_hour=args.quiet_hours_end)
        notified = notify_new_discoveries(
            session, ranker=TfidfRanker(), threshold=args.threshold, quiet_hours=quiet_hours
        )
        print(f"Notified for {len(notified)} job(s): {', '.join(notified)}" if notified else "No new notifications this run.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
