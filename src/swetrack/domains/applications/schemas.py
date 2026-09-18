"""Validated, immutable read/write schemas for the application pipeline domain.

Decoupled from the SQLAlchemy ORM models in ``models.py`` for the same
reason as the learning domain's schemas: callers get a frozen Pydantic
snapshot, never a session-bound ORM instance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# CLAUDE.md Phase 12's status list, in the rough order a pipeline usually moves
# through. Order here is documentation only -- transitions are not restricted
# to this sequence (see services.transition_status).
ApplicationStatus = Literal[
    "discovered",
    "interested",
    "applied",
    "oa",
    "recruiter_screen",
    "technical",
    "system_design",
    "behavioral",
    "final",
    "offer",
    "rejected",
    "withdrawn",
]


class Application(BaseModel):
    """One tracked application to a job, with its current pipeline status."""

    model_config = ConfigDict(frozen=True)

    id: str
    job_id: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class ApplicationStatusEvent(BaseModel):
    """One immutable status transition in an application's history.

    ``from_status`` is ``None`` for the event recorded at creation time.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    application_id: str
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    timestamp: datetime
    notes: str = ""


class CreateApplicationRequest(BaseModel):
    """Request body for ``POST /applications``."""

    job_id: str = Field(..., min_length=1)
    status: ApplicationStatus = "discovered"
    notes: str = ""


class TransitionStatusRequest(BaseModel):
    """Request body for ``POST /applications/{id}/status``."""

    status: ApplicationStatus
    notes: str = ""
