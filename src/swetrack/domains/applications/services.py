"""Application pipeline service layer: the only way callers write to this domain.

``create_application`` validates ``job_id`` against either the on-disk
sample job corpus (the same source ``opportunities`` reads from) or a
persisted, DB-backed discovered job (Job Radar Checkpoint 2) -- mirroring
how ``learning.services.create_activity`` validates ``skill_ids`` against
the canonical skill taxonomy.

No ML here (CLAUDE.md Phase 12: "Avoid premature ML on application outcomes
until enough real data exists") and no enforced status transition graph:
``transition_status`` accepts any ``to_status`` from any current status. A
real recruiting pipeline is not strictly linear -- a candidate can be
rejected and later reconsidered for a different role, or self-report
"interested" after "applied" for a variant posting -- and encoding a state
machine now would be exactly the kind of premature complexity CLAUDE.md
warns against. The full transition history is preserved regardless, so nothing
about this choice is lost if a stricter graph is added later.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from swetrack.domains.applications.models import ApplicationRecord, ApplicationStatusEventRecord
from swetrack.domains.applications.schemas import Application, ApplicationStatus, ApplicationStatusEvent
from swetrack.domains.jobs.models import DiscoveredJobRecord
from swetrack.domains.opportunities.config import DataLoadError, load_jobs


def _job_exists(session: Session, job_id: str) -> bool:
    try:
        jobs = load_jobs()
        if any(job.job_id == job_id for job in jobs):
            return True
    except DataLoadError:
        pass
    return session.query(DiscoveredJobRecord).filter(DiscoveredJobRecord.canonical_key == job_id).first() is not None


def create_application(
    session: Session,
    *,
    job_id: str,
    status: ApplicationStatus = "discovered",
    notes: str = "",
) -> tuple[Application, ApplicationStatusEvent]:
    """Create an application to ``job_id`` and record its initial status event.

    Raises ``ValueError`` if ``job_id`` does not match a known job. Atomic:
    the ``ApplicationRecord`` and its creation ``ApplicationStatusEventRecord``
    commit together or not at all.
    """
    if not _job_exists(session, job_id):
        raise ValueError(f"Unknown job id: {job_id!r}")

    try:
        application_record = ApplicationRecord(job_id=job_id, status=status)
        session.add(application_record)
        session.flush()  # assign application_record.id without committing yet

        event_record = ApplicationStatusEventRecord(
            application_id=application_record.id, from_status=None, to_status=status, notes=notes
        )
        session.add(event_record)
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(application_record)
    session.refresh(event_record)
    return _to_application(application_record), _to_status_event(event_record)


def transition_status(
    session: Session,
    *,
    application_id: str,
    to_status: ApplicationStatus,
    notes: str = "",
) -> tuple[Application, ApplicationStatusEvent]:
    """Move an application to ``to_status``, appending one immutable history event.

    Raises ``ValueError`` if the application does not exist. Atomic: the
    ``ApplicationRecord`` status update and the new
    ``ApplicationStatusEventRecord`` commit together or not at all.
    """
    application_record = session.get(ApplicationRecord, application_id)
    if application_record is None:
        raise ValueError(f"Unknown application id: {application_id!r}")

    try:
        event_record = ApplicationStatusEventRecord(
            application_id=application_record.id,
            from_status=application_record.status,
            to_status=to_status,
            notes=notes,
        )
        session.add(event_record)
        application_record.status = to_status
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(application_record)
    session.refresh(event_record)
    return _to_application(application_record), _to_status_event(event_record)


def get_application(session: Session, application_id: str) -> Application | None:
    record = session.get(ApplicationRecord, application_id)
    return _to_application(record) if record is not None else None


def list_applications(
    session: Session,
    *,
    status: ApplicationStatus | None = None,
    job_id: str | None = None,
) -> list[Application]:
    """List applications, optionally filtered by current status and/or job.

    Ordered by ``created_at`` ascending, with ``id`` as a deterministic
    tie-break for applications created in the same instant.
    """
    query = session.query(ApplicationRecord)
    if status is not None:
        query = query.filter(ApplicationRecord.status == status)
    if job_id is not None:
        query = query.filter(ApplicationRecord.job_id == job_id)
    records = query.order_by(ApplicationRecord.created_at.asc(), ApplicationRecord.id.asc()).all()
    return [_to_application(record) for record in records]


def get_application_history(session: Session, application_id: str) -> list[ApplicationStatusEvent]:
    """Return an application's full immutable status history in chronological order."""
    records = (
        session.query(ApplicationStatusEventRecord)
        .filter(ApplicationStatusEventRecord.application_id == application_id)
        .order_by(ApplicationStatusEventRecord.timestamp.asc())
        .all()
    )
    return [_to_status_event(record) for record in records]


def _to_application(record: ApplicationRecord) -> Application:
    return Application(
        id=record.id,
        job_id=record.job_id,
        status=record.status,  # type: ignore[arg-type]
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_status_event(record: ApplicationStatusEventRecord) -> ApplicationStatusEvent:
    return ApplicationStatusEvent(
        id=record.id,
        application_id=record.application_id,
        from_status=record.from_status,  # type: ignore[arg-type]
        to_status=record.to_status,  # type: ignore[arg-type]
        timestamp=record.timestamp,
        notes=record.notes,
    )
