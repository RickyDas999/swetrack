"""SQLAlchemy ORM model backing interview tracking (CLAUDE.md Phase 13).

An ``InterviewRecord`` is a single logged interview round. Unlike
``ApplicationRecord``/``ApplicationStatusEventRecord``'s separate mutable
state + immutable history, an interview is logged once with its outcome
already known (or ``"pending"`` if not yet decided) -- there is no pipeline
of transitions to track here, so one row is enough.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from swetrack.infrastructure.database.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InterviewRecord(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    application_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("applications.id"), nullable=True, index=True, default=None
    )
    company: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    round_type: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    skills_tested: Mapped[list[str]] = mapped_column(JSON, default=list)
    result: Mapped[str] = mapped_column(String, default="pending")
    notes: Mapped[str] = mapped_column(String, default="")
    feedback: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
