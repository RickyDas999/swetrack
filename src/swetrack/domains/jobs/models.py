"""SQLAlchemy ORM model backing persisted, deduplicated discovered jobs.

Named ``discovered_jobs`` (not ``jobs``) to stay unambiguous from the
existing CSV-backed ``opportunities.models.JobRecord`` concept -- see
docs/job-radar-integration-plan.md Section 6. ``canonical_key``
(``"{source_type}:{source_job_id}"``) doubles as the value stored in
``ApplicationRecord.job_id`` for jobs discovered this way, so no schema
change was needed there.

No separate ``normalized_title``/``normalized_company`` columns and no
``description_hash`` column: services.py normalizes/compares in Python
against the small number of existing rows at sync time.
ponytail: an O(n) full-table scan per sync, fine at this project's scale (a
personal job search, not a production job board) -- add indexed normalized
columns if a sync ever needs to scan thousands of rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from swetrack.infrastructure.database.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiscoveredJobRecord(Base):
    __tablename__ = "discovered_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    canonical_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String, index=True)
    source_job_id: Mapped[str] = mapped_column(String)
    company_name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    location_text: Mapped[str] = mapped_column(String, default="")
    workplace_type: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    description_plain: Mapped[str] = mapped_column(Text, default="")
    application_url: Mapped[str] = mapped_column(String, default="")
    source_url: Mapped[str] = mapped_column(String, default="")
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    # Soft closure (SWETrack_Job_Radar_Claude_Code_Handoff.md Section 16:
    # "Make deletions soft/recoverable"). Column only for now -- the
    # detect-and-mark-closed logic (a job absent from its source's latest
    # sync) is deferred to a later checkpoint alongside eligibility/inbox
    # filtering, which is where it first has a consumer.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    # Cross-source duplicate detection: a link to the earliest-seen row,
    # not a merged multi-provenance record -- see services.py's
    # _find_cross_source_duplicate for the matching rules and rationale.
    duplicate_of_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
