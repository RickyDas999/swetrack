"""CLI: fetch and print normalized jobs from one ATS source. No DB writes.

Job Radar Checkpoint 1's acceptance criterion
(SWETrack_Job_Radar_Claude_Code_Handoff.md): "`swetrack jobs sync --dry-run`
prints normalized jobs without DB writes." This is that command's first
slice: one source (Greenhouse), one company at a time via CLI flags rather
than the source registry YAML, which is a later slice
(docs/job-radar-integration-plan.md Section 12). Persistence lands in
Checkpoint 2, so --dry-run is required until then.

    python scripts/jobs_fetch.py --token exampleco --company "Example Co" --dry-run
"""

from __future__ import annotations

import argparse
import sys

from swetrack.domains.jobs.adapters.greenhouse import GreenhouseAdapter
from swetrack.domains.jobs.schemas import NormalizedJob

_ADAPTERS = {"greenhouse": GreenhouseAdapter}


def _print_job(job: NormalizedJob) -> None:
    print(f"[{job.source_type}] {job.company_name} -- {job.title}")
    print(f"    location: {job.location_text or '(unspecified)'}")
    print(f"    posted:   {job.source_published_at or '(unknown)'}   updated: {job.source_updated_at or '(unknown)'}")
    print(f"    url:      {job.application_url}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="greenhouse", choices=sorted(_ADAPTERS))
    parser.add_argument("--token", required=True, help="ATS board token / site identifier")
    parser.add_argument("--company", required=True, help="Display company name (not returned by the ATS API)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print normalized jobs only. Currently required -- there is no persistence layer yet (Checkpoint 2).",
    )
    args = parser.parse_args(argv)

    if not args.dry_run:
        parser.error("--dry-run is required until Job Radar Checkpoint 2 adds persistence")

    adapter_cls = _ADAPTERS[args.source]
    adapter = adapter_cls(args.token, args.company)
    jobs = adapter.fetch()

    print(f"Fetched {len(jobs)} job(s) from {args.source}:{args.token}\n")
    for job in jobs:
        _print_job(job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
