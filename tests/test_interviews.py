from __future__ import annotations

from datetime import datetime, timezone

import pytest

from swetrack.domains.applications.services import create_application
from swetrack.domains.interviews.services import create_interview, get_interview, list_interviews
from swetrack.domains.learning.services import get_mastery, get_skill_events
from swetrack.domains.opportunities.config import DEFAULT_JOBS_PATH, load_jobs

KNOWN_JOB_ID = load_jobs(DEFAULT_JOBS_PATH)[0].job_id
NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def test_create_interview_rejects_unknown_skill_id(db_session):
    with pytest.raises(ValueError, match="Unknown skill id"):
        create_interview(
            db_session,
            company="Figma",
            role="SWE",
            round_type="coding",
            date=NOW,
            skills_tested=["not-a-real-skill"],
        )


def test_create_interview_rejects_unknown_application_id(db_session):
    with pytest.raises(ValueError, match="Unknown application id"):
        create_interview(
            db_session,
            company="Figma",
            role="SWE",
            round_type="coding",
            date=NOW,
            skills_tested=[],
            application_id="does-not-exist",
        )


def test_create_interview_defaults_to_pending_and_emits_no_skill_events(db_session):
    interview, events = create_interview(
        db_session, company="Figma", role="SWE", round_type="coding", date=NOW, skills_tested=["graphs"]
    )

    assert interview.result == "pending"
    assert events == []
    assert get_skill_events(db_session, "graphs") == []
    assert get_mastery(db_session, "graphs") is None


def test_create_interview_with_passed_result_emits_skill_events_and_updates_mastery(db_session):
    interview, events = create_interview(
        db_session,
        company="Figma",
        role="SWE",
        round_type="coding",
        date=NOW,
        skills_tested=["graphs", "hash-maps"],
        result="passed",
    )

    assert {event.skill_id for event in events} == {"graphs", "hash-maps"}
    assert all(event.source_type == "interview_feedback" for event in events)
    assert all(event.source_id == interview.id for event in events)
    assert all(event.outcome == 1.0 for event in events)
    assert get_mastery(db_session, "graphs") is not None


def test_create_interview_with_failed_result_emits_zero_outcome_skill_events(db_session):
    _, events = create_interview(
        db_session, company="Figma", role="SWE", round_type="coding", date=NOW, skills_tested=["graphs"], result="failed"
    )

    assert events[0].outcome == 0.0


def test_create_interview_links_to_application(db_session):
    application, _ = create_application(db_session, job_id=KNOWN_JOB_ID)

    interview, _ = create_interview(
        db_session,
        company="Figma",
        role="SWE",
        round_type="coding",
        date=NOW,
        skills_tested=[],
        application_id=application.id,
    )

    assert interview.application_id == application.id


def test_get_interview_returns_none_when_missing(db_session):
    assert get_interview(db_session, "does-not-exist") is None


def test_list_interviews_filters_by_application_id_and_round_type(db_session):
    application, _ = create_application(db_session, job_id=KNOWN_JOB_ID)
    i_a, _ = create_interview(
        db_session,
        company="Figma",
        role="SWE",
        round_type="coding",
        date=NOW,
        skills_tested=[],
        application_id=application.id,
    )
    i_b, _ = create_interview(
        db_session, company="TikTok", role="SWE", round_type="behavioral", date=NOW, skills_tested=[]
    )

    all_interviews = list_interviews(db_session)
    assert {i.id for i in all_interviews} == {i_a.id, i_b.id}

    by_application = list_interviews(db_session, application_id=application.id)
    assert {i.id for i in by_application} == {i_a.id}

    by_round_type = list_interviews(db_session, round_type="behavioral")
    assert {i.id for i in by_round_type} == {i_b.id}
