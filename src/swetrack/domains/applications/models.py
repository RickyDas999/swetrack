"""SQLAlchemy ORM models backing the application/recruiting pipeline (CLAUDE.md Phase 12).

Unlike the learning domain's ``SkillMasteryRecord`` (a recomputable cache
derived by replaying immutable ``SkillEvent`` rows), ``ApplicationRecord.status``
here is simply the current state of a real-world process with no model to
recompute it from -- there is nothing to "replay" a recruiting pipeline
into. It is kept as the mutable source of truth for "what is this
application's status right now," while ``ApplicationStatusEventRecord`` is
an append-only audit trail of every transition, giving a full timeline
without requiring one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from swetrack.infrastructure.database.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    job_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ApplicationStatusEventRecord(Base):
    """One immutable status transition. ``from_status`` is null on the creation event."""

    __tablename__ = "application_status_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    application_id: Mapped[str] = mapped_column(String, ForeignKey("applications.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    to_status: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    notes: Mapped[str] = mapped_column(String, default="")
