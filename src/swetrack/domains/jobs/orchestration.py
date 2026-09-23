"""Shared per-source sync orchestration: fetch + persist + health tracking.

Job Radar Checkpoint 8 (hardening). Before this, scripts/jobs_fetch.py's
registry mode and scripts/jobs_sync_and_notify.py each implemented their
own fetch-and-sync loop, and *neither* caught a per-source failure -- one
flaky ATS board would raise out of the loop and abort the entire run,
including sources that would otherwise have succeeded. This consolidates
both into one tested function where a single source's failure is recorded
(via source_health) and skipped, never fatal to the run.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from swetrack.domains.jobs.registry import build_adapter
from swetrack.domains.jobs.schemas import SourceRegistryEntry, SyncResult
from swetrack.domains.jobs.services import sync_source
from swetrack.domains.jobs.source_health import record_sync_attempt


def _source_key(entry: SourceRegistryEntry) -> str:
    return f"{entry.adapter}:{entry.token or entry.site or entry.board_name}"


@dataclass(frozen=True)
class SourceSyncOutcome:
    entry: SourceRegistryEntry
    result: SyncResult | None
    error: str | None


def sync_registry_sources(session: Session, entries: list[SourceRegistryEntry]) -> list[SourceSyncOutcome]:
    """Fetch + persist every enabled entry, one at a time. A failing source is recorded, never fatal."""
    outcomes: list[SourceSyncOutcome] = []
    for entry in entries:
        if not entry.enabled:
            continue

        source_key = _source_key(entry)
        try:
            jobs = build_adapter(entry).fetch()
            result = sync_source(session, source_type=entry.adapter, jobs=jobs)
        except Exception as exc:  # noqa: BLE001 -- one flaky source must never abort the whole run
            record_sync_attempt(
                session, source_key=source_key, company_name=entry.company, adapter_type=entry.adapter,
                success=False, error=str(exc),
            )
            outcomes.append(SourceSyncOutcome(entry=entry, result=None, error=str(exc)))
            continue

        record_sync_attempt(
            session, source_key=source_key, company_name=entry.company, adapter_type=entry.adapter, success=True
        )
        outcomes.append(SourceSyncOutcome(entry=entry, result=result, error=None))

    return outcomes
