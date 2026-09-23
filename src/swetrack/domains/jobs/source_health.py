"""Per-source sync health tracking: last polled/success time, last error, failure streak.

Job Radar Checkpoint 8's "source health dashboard." A registry entry's
identity here (``source_key``) is the same shape ``discovered_jobs.canonical_key``
uses one level up: ``{adapter}:{token|site|board_name}``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from swetrack.domains.jobs.models import JobSourceHealthRecord
from swetrack.domains.jobs.normalize import ensure_utc


class SourceHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_key: str
    company_name: str
    adapter_type: str
    last_polled_at: datetime
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    total_success_count: int
    total_failure_count: int


def record_sync_attempt(
    session: Session,
    *,
    source_key: str,
    company_name: str,
    adapter_type: str,
    success: bool,
    error: str | None = None,
) -> SourceHealth:
    """Upsert one source's health row after one fetch attempt."""
    record = session.get(JobSourceHealthRecord, source_key)
    now = datetime.now(timezone.utc)
    if record is None:
        record = JobSourceHealthRecord(
            source_key=source_key,
            company_name=company_name,
            adapter_type=adapter_type,
            consecutive_failures=0,
            total_success_count=0,
            total_failure_count=0,
        )
        session.add(record)

    record.company_name = company_name
    record.adapter_type = adapter_type
    record.last_polled_at = now
    if success:
        record.last_success_at = now
        record.last_error = None
        record.consecutive_failures = 0
        record.total_success_count += 1
    else:
        record.last_error = error
        record.consecutive_failures += 1
        record.total_failure_count += 1

    session.commit()
    session.refresh(record)
    return _to_source_health(record)


def list_source_health(session: Session) -> list[SourceHealth]:
    records = session.query(JobSourceHealthRecord).order_by(JobSourceHealthRecord.company_name.asc()).all()
    return [_to_source_health(record) for record in records]


def _to_source_health(record: JobSourceHealthRecord) -> SourceHealth:
    return SourceHealth(
        source_key=record.source_key,
        company_name=record.company_name,
        adapter_type=record.adapter_type,
        last_polled_at=ensure_utc(record.last_polled_at),
        last_success_at=ensure_utc(record.last_success_at),
        last_error=record.last_error,
        consecutive_failures=record.consecutive_failures,
        total_success_count=record.total_success_count,
        total_failure_count=record.total_failure_count,
    )
