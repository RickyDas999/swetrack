from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from swetrack.domains.applications.priority import compute_application_priority
from swetrack.domains.applications.schemas import Application
from swetrack.domains.learning.services import create_activity, record_attempt
from swetrack.domains.opportunities.models import CandidateProfile, JobRecord
from swetrack.domains.opportunities.ranking.tfidf import TfidfRanker

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_TODAY = date(2026, 1, 1)

_JOB = JobRecord(
    job_id="JOB-TEST",
    company="TestCo",
    title="Junior Backend Engineer",
    location="Remote",
    description="Build REST APIs in Python and Java.",
    skills=["Python", "Java", "REST APIs", "PostgreSQL", "Docker", "AWS Lambda", "Git"],
    experience_level="Entry-level",
    source="synthetic",
    compensation_min=90000,
    compensation_max=115000,
    application_deadline=date(2026, 1, 8),  # 7 days after _TODAY
)

_PROFILE = CandidateProfile(
    skills=["Python", "Java", "AWS", "SQL"],
    experience="New grad backend engineer with Python and Java experience.",
    preferred_roles=["Backend Engineer"],
    preferred_locations=["Remote"],
    preferred_companies=["TestCo"],
    minimum_compensation=100000,
)


def _application(status: str = "discovered") -> Application:
    return Application(id="app-test", job_id=_JOB.job_id, status=status, created_at=_NOW, updated_at=_NOW)


def _priority(db_session, *, job: JobRecord = _JOB, profile: CandidateProfile = _PROFILE, today: date = _TODAY):
    return compute_application_priority(
        db_session, application=_application(), job=job, profile=profile, ranker=TfidfRanker(), today=today
    )


def test_compute_application_priority_components_match_underlying_readiness(db_session):
    result = _priority(db_session)

    assert result.application_id == "app-test"
    assert result.job_id == "JOB-TEST"
    assert result.status == "discovered"
    assert 0.0 <= result.score <= 1.0
    assert result.components.role_fit == pytest.approx(result.readiness.fit_score)
    assert result.components.readiness == pytest.approx(result.readiness.readiness_score)


def test_compute_application_priority_preference_match_is_full_when_role_and_location_match(db_session):
    result = _priority(db_session)

    # _PROFILE's preferred role "Backend Engineer" and location "Remote" both match _JOB.
    assert result.components.user_preference == pytest.approx(1.0)


def test_compute_application_priority_preference_match_is_neutral_with_no_stated_preferences(db_session):
    profile_no_preferences = CandidateProfile(skills=["Python", "Java"], experience="New grad backend engineer.")

    result = _priority(db_session, profile=profile_no_preferences)

    assert result.components.user_preference == pytest.approx(0.5)


def test_compute_application_priority_company_interest_matches_preferred_company(db_session):
    result = _priority(db_session)

    # _PROFILE's preferred_companies includes "TestCo", the _JOB's company.
    assert result.components.company_interest == pytest.approx(1.0)


def test_compute_application_priority_company_interest_is_zero_for_unmatched_preference(db_session):
    profile_other_company = _PROFILE.model_copy(update={"preferred_companies": ["SomeOtherCo"]})

    result = _priority(db_session, profile=profile_other_company)

    assert result.components.company_interest == pytest.approx(0.0)


def test_compute_application_priority_company_interest_is_neutral_with_no_stated_preference(db_session):
    profile_no_company_preference = _PROFILE.model_copy(update={"preferred_companies": []})

    result = _priority(db_session, profile=profile_no_company_preference)

    assert result.components.company_interest == pytest.approx(0.5)


def test_compute_application_priority_compensation_fit_when_job_clears_minimum(db_session):
    # _JOB.compensation_max=115000 >= _PROFILE.minimum_compensation=100000.
    result = _priority(db_session)

    assert result.components.compensation_fit == pytest.approx(1.0)


def test_compute_application_priority_compensation_fit_when_job_falls_short(db_session):
    profile_high_minimum = _PROFILE.model_copy(update={"minimum_compensation": 200000})

    result = _priority(db_session, profile=profile_high_minimum)

    assert result.components.compensation_fit == pytest.approx(0.0)


def test_compute_application_priority_compensation_fit_is_neutral_with_no_data(db_session):
    profile_no_minimum = _PROFILE.model_copy(update={"minimum_compensation": None})
    job_no_compensation = _JOB.model_copy(update={"compensation_min": None, "compensation_max": None})

    result = _priority(db_session, job=job_no_compensation, profile=profile_no_minimum)

    assert result.components.compensation_fit == pytest.approx(0.5)


def test_compute_application_priority_deadline_urgency_rises_as_deadline_nears(db_session):
    far_off = _priority(db_session, today=date(2025, 12, 1))  # 38 days before the deadline
    near = _priority(db_session, today=date(2026, 1, 7))  # 1 day before the deadline

    assert 0.0 <= far_off.components.deadline_urgency < near.components.deadline_urgency <= 1.0


def test_compute_application_priority_deadline_urgency_is_zero_once_passed(db_session):
    result = _priority(db_session, today=date(2026, 2, 1))  # after the deadline

    assert result.components.deadline_urgency == pytest.approx(0.0)


def test_compute_application_priority_deadline_urgency_is_zero_with_no_deadline(db_session):
    job_no_deadline = _JOB.model_copy(update={"application_deadline": None})

    result = _priority(db_session, job=job_no_deadline)

    assert result.components.deadline_urgency == pytest.approx(0.0)


def test_compute_application_priority_rises_with_improved_mastery(db_session):
    activity = create_activity(
        db_session, slug="python-review", title="Python Review", activity_type="concept_review", skill_ids=["python"]
    )
    baseline = _priority(db_session)

    for _ in range(10):
        record_attempt(db_session, activity_id=activity.id, success=True)

    improved = _priority(db_session)

    assert improved.score > baseline.score
