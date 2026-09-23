"""CLI: refresh the public, non-personal job discovery feed (public/latest_jobs.json).

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 5 / Checkpoint 7. This is
the script the (optional, off-by-default) GitHub Actions workflow
(.github/workflows/public-discovery.yml) runs. It deliberately imports
nothing from infrastructure.database (no SQLite session, ever touches
var/swetrack.db), resume/, or the named config/candidate.example.yaml --
only public source-registry + adapter + eligibility/normalization logic
that never sees private data. See domains/jobs/public_feed.py's own
docstring for the structural guarantee this relies on.

    python scripts/public_discovery.py
    python scripts/public_discovery.py --registry config/sources.example.yaml --out public/latest_jobs.json
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from swetrack.domains.jobs.public_feed import (
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_MAX_ENTRIES,
    PublicFeed,
    apply_retention,
    contains_forbidden_content,
    generic_candidate,
    merge_feed_entries,
    to_public_feed_entry,
)
from swetrack.domains.jobs.registry import DEFAULT_SOURCES_PATH, build_adapter, load_source_registry
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_OUT_PATH = find_repo_root() / "public" / "latest_jobs.json"


def _load_previous_feed(path: Path) -> list:
    if not path.exists():
        return []
    return PublicFeed.model_validate_json(path.read_text(encoding="utf-8")).jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=DEFAULT_SOURCES_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    parser.add_argument("--max-age-days", type=float, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    candidate = generic_candidate(year=now.year)

    entries_raw = load_source_registry(args.registry)
    fresh_entries = []
    for source in entries_raw:
        if not source.enabled:
            continue
        try:
            jobs = build_adapter(source).fetch()
        except Exception as exc:  # noqa: BLE001 -- one flaky public source must not fail the whole run
            print(f"WARNING: {source.company} ({source.adapter}) failed: {exc}", file=sys.stderr)
            continue
        for job in jobs:
            entry = to_public_feed_entry(job, candidate=candidate, now=now)
            if entry is not None:
                fresh_entries.append(entry)

    previous_entries = _load_previous_feed(args.out)
    merged = merge_feed_entries(previous_entries, fresh_entries, now=now)
    retained = apply_retention(merged, now=now, max_age_days=args.max_age_days, max_entries=args.max_entries)

    feed = PublicFeed(generated_at=now, jobs=retained)
    feed_json = feed.model_dump_json(indent=2)

    violations = contains_forbidden_content(feed_json)
    if violations:
        print(f"REFUSING TO WRITE: forbidden content found in generated feed: {violations}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(feed_json + "\n", encoding="utf-8")
    print(f"Wrote {len(retained)} job(s) to {args.out} (fetched {len(fresh_entries)} eligible/uncertain this run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
