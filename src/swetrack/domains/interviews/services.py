"""Interview domain service layer: the only way callers write to this domain.

``create_interview`` validates ``skills_tested`` against the canonical skill
taxonomy (mirroring ``learning.services.create_activity``) and, when given,
``application_id`` against an existing application (mirroring
``applications.services.create_application``'s job_id check).

When ``result`` is ``"passed"`` or ``"failed"``, one immutable SkillEvent
(source_type ``"interview_feedback"``, per CLAUDE.md Phase 6) and one
sequential BKT mastery update is written per tested skill, reusing
``learning.services.apply_sequential_mastery_update`` -- the same mastery
machinery coding and system-design attempts use. A ``"pending"`` result (the
default) skips this: CLAUDE.md Phase 13 is explicit that mastery should not
be inferred before a real outcome is known.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from swetrack.domains.applications.models import ApplicationRecord
from swetrack.domains.interviews.models import InterviewRecord
from swetrack.domains.interviews.schemas import Interview, InterviewResult, RoundType
from swetrack.domains.learning.models import SkillEventRecord
from swetrack.domains.learning.schemas import SkillEvent
from swetrack.domains.learning.services import apply_sequential_mastery_update
from swetrack.domains.skills.normalization import get_skill_by_id
from swetrack.ml.knowledge_tracing.bkt import DEFAULT_PARAMETERS, BKTParameters

_SCORED_RESULTS = {"passed", "failed"}


def create_interview(
    session: Session,
    *,
    company: str,
    role: str,
    round_type: RoundType,
    date: datetime,
    skills_tested: list[str],
    result: InterviewResult = "pending",
    notes: str = "",
    feedback: str = "",
    application_id: str | None = None,
    evidence_weight: float = 1.0,
    bkt_params: BKTParameters = DEFAULT_PARAMETERS,
) -> tuple[Interview, list[SkillEvent]]:
    """Log one interview round, emitting SkillEvents only if its result is decided.

    Raises ``ValueError`` if any id in ``skills_tested`` is unknown, or if
    ``application_id`` is given but does not match an existing application.
    Atomic: the interview row and any SkillEvents/mastery updates commit
    together or not at all.
    """
    unknown_skills = [skill_id for skill_id in skills_tested if get_skill_by_id(skill_id) is None]
    if unknown_skills:
        raise ValueError(f"Unknown skill id(s): {unknown_skills}")
    if application_id is not None and session.get(ApplicationRecord, application_id) is None:
        raise ValueError(f"Unknown application id: {application_id!r}")

    try:
        interview_record = InterviewRecord(
            application_id=application_id,
            company=company,
            role=role,
            round_type=round_type,
            date=date,
            skills_tested=list(skills_tested),
            result=result,
            notes=notes,
            feedback=feedback,
        )
        session.add(interview_record)
        session.flush()  # assign interview_record.id without committing yet

        event_records: list[SkillEventRecord] = []
        if result in _SCORED_RESULTS:
            outcome = 1.0 if result == "passed" else 0.0
            event_records = [
                SkillEventRecord(
                    skill_id=skill_id,
                    source_type="interview_feedback",
                    source_id=interview_record.id,
                    outcome=outcome,
                    evidence_weight=evidence_weight,
                )
                for skill_id in skills_tested
            ]
            session.add_all(event_records)
            session.flush()  # surface any SkillEvent constraint violation before touching mastery

            for skill_id in skills_tested:
                apply_sequential_mastery_update(session, skill_id, correct=result == "passed", params=bkt_params)

        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(interview_record)
    for record in event_records:
        session.refresh(record)
    return _to_interview(interview_record), [_to_skill_event(record) for record in event_records]


def get_interview(session: Session, interview_id: str) -> Interview | None:
    record = session.get(InterviewRecord, interview_id)
    return _to_interview(record) if record is not None else None


def list_interviews(
    session: Session,
    *,
    application_id: str | None = None,
    round_type: RoundType | None = None,
) -> list[Interview]:
    """List interviews, optionally filtered by application and/or round type, oldest first."""
    query = session.query(InterviewRecord)
    if application_id is not None:
        query = query.filter(InterviewRecord.application_id == application_id)
    if round_type is not None:
        query = query.filter(InterviewRecord.round_type == round_type)
    records = query.order_by(InterviewRecord.date.asc(), InterviewRecord.id.asc()).all()
    return [_to_interview(record) for record in records]


def _to_interview(record: InterviewRecord) -> Interview:
    return Interview(
        id=record.id,
        application_id=record.application_id,
        company=record.company,
        role=record.role,
        round_type=record.round_type,  # type: ignore[arg-type]
        date=record.date,
        skills_tested=list(record.skills_tested),
        result=record.result,  # type: ignore[arg-type]
        notes=record.notes,
        feedback=record.feedback,
        created_at=record.created_at,
    )


def _to_skill_event(record: SkillEventRecord) -> SkillEvent:
    return SkillEvent(
        id=record.id,
        skill_id=record.skill_id,
        source_type=record.source_type,  # type: ignore[arg-type]
        source_id=record.source_id,
        timestamp=record.timestamp,
        outcome=record.outcome,
        evidence_weight=record.evidence_weight,
    )
