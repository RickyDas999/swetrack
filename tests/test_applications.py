from __future__ import annotations

import pytest

from swetrack.domains.applications.services import (
    create_application,
    get_application,
    get_application_history,
    list_applications,
    transition_status,
)
from swetrack.domains.opportunities.config import DEFAULT_JOBS_PATH, load_jobs

KNOWN_JOB_ID = load_jobs(DEFAULT_JOBS_PATH)[0].job_id
OTHER_JOB_ID = load_jobs(DEFAULT_JOBS_PATH)[1].job_id


def test_create_application_rejects_unknown_job_id(db_session):
    with pytest.raises(ValueError, match="Unknown job id"):
        create_application(db_session, job_id="NOT-A-REAL-JOB")


def test_create_application_defaults_to_discovered_status(db_session):
    application, event = create_application(db_session, job_id=KNOWN_JOB_ID)

    assert application.job_id == KNOWN_JOB_ID
    assert application.status == "discovered"
    assert event.from_status is None
    assert event.to_status == "discovered"
    assert event.application_id == application.id


def test_create_application_accepts_explicit_initial_status(db_session):
    application, event = create_application(db_session, job_id=KNOWN_JOB_ID, status="applied")

    assert application.status == "applied"
    assert event.to_status == "applied"


def test_transition_status_updates_current_status_and_appends_history(db_session):
    application, _ = create_application(db_session, job_id=KNOWN_JOB_ID)

    updated, event = transition_status(db_session, application_id=application.id, to_status="applied")

    assert updated.status == "applied"
    assert updated.id == application.id
    assert event.from_status == "discovered"
    assert event.to_status == "applied"

    history = get_application_history(db_session, application.id)
    assert [e.to_status for e in history] == ["discovered", "applied"]


def test_transition_status_allows_non_linear_moves(db_session):
    """No enforced state machine: rejected -> interested is a legal transition."""
    application, _ = create_application(db_session, job_id=KNOWN_JOB_ID, status="rejected")

    updated, event = transition_status(db_session, application_id=application.id, to_status="interested")

    assert updated.status == "interested"
    assert event.from_status == "rejected"


def test_transition_status_unknown_application_raises(db_session):
    with pytest.raises(ValueError, match="Unknown application id"):
        transition_status(db_session, application_id="does-not-exist", to_status="applied")


def test_get_application_returns_none_when_missing(db_session):
    assert get_application(db_session, "does-not-exist") is None


def test_get_application_history_is_chronological(db_session):
    application, _ = create_application(db_session, job_id=KNOWN_JOB_ID)
    transition_status(db_session, application_id=application.id, to_status="applied")
    transition_status(db_session, application_id=application.id, to_status="oa")

    history = get_application_history(db_session, application.id)

    assert [e.to_status for e in history] == ["discovered", "applied", "oa"]
    assert history == sorted(history, key=lambda e: e.timestamp)


def test_list_applications_filters_by_status_and_job_id(db_session):
    app_a, _ = create_application(db_session, job_id=KNOWN_JOB_ID, status="applied")
    app_b, _ = create_application(db_session, job_id=OTHER_JOB_ID, status="applied")
    app_c, _ = create_application(db_session, job_id=KNOWN_JOB_ID, status="discovered")

    all_applications = list_applications(db_session)
    assert {a.id for a in all_applications} == {app_a.id, app_b.id, app_c.id}

    applied_only = list_applications(db_session, status="applied")
    assert {a.id for a in applied_only} == {app_a.id, app_b.id}

    known_job_only = list_applications(db_session, job_id=KNOWN_JOB_ID)
    assert {a.id for a in known_job_only} == {app_a.id, app_c.id}
