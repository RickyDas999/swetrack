"""CLI: fetch jobs from ATS sources, printing them (--dry-run) or persisting them.

SWETrack_Job_Radar_Claude_Code_Handoff.md's Checkpoint 1 acceptance
criterion: "`swetrack jobs sync --dry-run` prints normalized jobs without DB
writes." Omitting --dry-run now upserts into `discovered_jobs` via
domains.jobs.services.sync_source (Checkpoint 2) -- idempotent, safe to
run repeatedly, and auto-creates a "discovered" application per new job.

Two modes:

Registry mode -- poll every enabled source in a registry YAML
(config/sources.example.yaml by default):

    python scripts/jobs_fetch.py --registry --dry-run
    python scripts/jobs_fetch.py --registry               # writes to the DB
    python scripts/jobs_fetch.py --registry config/sources.yaml --dry-run

Ad-hoc mode -- one source at a time via flags, or a manual URL/pasted-JD import:

    python scripts/jobs_fetch.py --source greenhouse --token exampleco --company "Example Co" --dry-run
    python scripts/jobs_fetch.py --source lever --token exampleco --company "Example Co"
    python scripts/jobs_fetch.py --source manual --url "https://example.com/careers/123" \\
        --company "Example Co" --title "Software Engineer, New Grad" --dry-run
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from swetrack.domains.jobs.adapters.ashby import AshbyAdapter
from swetrack.domains.jobs.adapters.base import SourceAdapter
from swetrack.domains.jobs.adapters.greenhouse import GreenhouseAdapter
from swetrack.domains.jobs.adapters.lever import LeverAdapter
from swetrack.domains.jobs.adapters.manual import ManualAdapter
from swetrack.domains.jobs.registry import DEFAULT_SOURCES_PATH, build_adapter, load_source_registry
from swetrack.domains.jobs.schemas import NormalizedJob, SyncResult
from swetrack.domains.jobs.services import sync_source
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db

_ADAPTERS = {"greenhouse": GreenhouseAdapter, "lever": LeverAdapter, "ashby": AshbyAdapter}


def _print_job(job: NormalizedJob) -> None:
    print(f"[{job.source_type}] {job.company_name} -- {job.title}")
    print(f"    location: {job.location_text or '(unspecified)'}")
    print(f"    posted:   {job.source_published_at or '(unknown)'}   updated: {job.source_updated_at or '(unknown)'}")
    print(f"    url:      {job.application_url}")
    print()


def _print_sync_result(result: SyncResult, label: str) -> None:
    print(
        f"{label}: fetched={result.total_fetched} new={result.new_count} "
        f"updated={result.updated_count} unchanged={result.unchanged_count} duplicate={result.duplicate_count}"
    )


def _open_session() -> Session:
    engine = get_engine()
    init_db(engine)
    return get_sessionmaker(engine)()


def _build_ad_hoc_adapter(args: argparse.Namespace, parser: argparse.ArgumentParser) -> SourceAdapter:
    if args.company is None:
        parser.error("--company is required")

    if args.source == "manual":
        if not args.url or not args.title:
            parser.error("--source manual requires --url and --title")
        return ManualAdapter(
            url=args.url,
            company_name=args.company,
            title=args.title,
            description=args.description,
            location=args.location,
        )

    if not args.token:
        parser.error(f"--source {args.source} requires --token")
    return _ADAPTERS[args.source](args.token, args.company)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--registry",
        nargs="?",
        const=str(DEFAULT_SOURCES_PATH),
        default=None,
        metavar="PATH",
        help=f"Poll every enabled source in a registry YAML (default: {DEFAULT_SOURCES_PATH}) "
        "instead of one ad-hoc --source",
    )
    parser.add_argument("--source", default="greenhouse", choices=[*_ADAPTERS, "manual"])
    parser.add_argument(
        "--token", help="Source identifier: Greenhouse board token, Lever site, or Ashby job-board name"
    )
    parser.add_argument("--company", help="Display company name (not returned by the ATS API)")
    parser.add_argument("--url", help="Job URL (--source manual only)")
    parser.add_argument("--title", help="Job title (--source manual only)")
    parser.add_argument("--description", default="", help="Pasted job description text (--source manual only)")
    parser.add_argument("--location", default="", help="Job location text (--source manual only)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print normalized jobs only, without writing to the database.",
    )
    args = parser.parse_args(argv)

    if args.registry is not None:
        entries = load_source_registry(args.registry)
        enabled = [entry for entry in entries if entry.enabled]

        if args.dry_run:
            total = 0
            for entry in enabled:
                jobs = build_adapter(entry).fetch()
                print(f"Fetched {len(jobs)} job(s) from {entry.adapter}:{entry.company}\n")
                for job in jobs:
                    _print_job(job)
                total += len(jobs)
            print(f"Total: {total} job(s) across {len(enabled)} enabled source(s) ({len(entries)} configured)")
            return 0

        session = _open_session()
        try:
            for entry in enabled:
                jobs = build_adapter(entry).fetch()
                result = sync_source(session, source_type=entry.adapter, jobs=jobs)
                _print_sync_result(result, entry.company)
        finally:
            session.close()
        return 0

    adapter = _build_ad_hoc_adapter(args, parser)
    jobs = adapter.fetch()

    if args.dry_run:
        print(f"Fetched {len(jobs)} job(s) from {args.source}\n")
        for job in jobs:
            _print_job(job)
        return 0

    session = _open_session()
    try:
        result = sync_source(session, source_type=args.source, jobs=jobs)
        _print_sync_result(result, args.company or args.source)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
