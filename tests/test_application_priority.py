from __future__ import annotations

from datetime import datetime, timezone

import pytest

from swetrack.domains.applications.priority import compute_application_priority
from swetrack.domains.applications.schemas import Application
from swetrack.domains.learning.services import create_activity, record_attempt
from swetrack.domains.opportunities.models import CandidateProfile, JobRecord
from swetrack.domains.opportunities.ranking.tfidf import TfidfRanker

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_JOB = JobRecord(
    job_id="JOB-TEST",
    company="TestCo",
    title="Junior Backend Engineer",
    location="Remote",
    description="Build REST APIs in Python and Java.",
    skills=["Python", "Java", "REST APIs", "PostgreSQL", "Docker", "AWS Lambda", "Git"],
    experience_level="Entry-level",
    source="synthetic",
)

_PROFILE = CandidateProfile(
    skills=["Python", "Java", "AWS", "SQL"],
    experience="New grad backend engineer with Python and Java experience.",
    preferred_roles=["Backend Engineer"],
    preferred_locations=["Remote"],
)


def _application(status: str = "discovered") -> Application:
    return Application(id="app-test", job_id=_JOB.job_id, status=status, created_at=_NOW, updated_at=_NOW)


def test_compute_application_priority_components_match_underlying_readiness(db_session):
    result = compute_application_priority(
        db_session, application=_application(), job=_JOB, profile=_PROFILE, ranker=TfidfRanker()
    )

    assert result.application_id == "app-test"
    assert result.job_id == "JOB-TEST"
    assert result.status == "discovered"
    assert 0.0 <= result.score <= 1.0
    assert result.components.role_fit == pytest.approx(result.readiness.fit_score)
    assert result.components.readiness == pytest.approx(result.readiness.readiness_score)


def test_compute_application_priority_preference_match_is_full_when_role_and_location_match(db_session):
    result = compute_application_priority(
        db_session, application=_application(), job=_JOB, profile=_PROFILE, ranker=TfidfRanker()
    )

    # _PROFILE's preferred role "Backend Engineer" and location "Remote" both match _JOB.
    assert result.components.user_preference == pytest.approx(1.0)


def test_compute_application_priority_preference_match_is_neutral_with_no_stated_preferences(db_session):
    profile_no_preferences = CandidateProfile(skills=["Python", "Java"], experience="New grad backend engineer.")

    result = compute_application_priority(
        db_session, application=_application(), job=_JOB, profile=profile_no_preferences, ranker=TfidfRanker()
    )

    assert result.components.user_preference == pytest.approx(0.5)


def test_compute_application_priority_rises_with_improved_mastery(db_session):
    activity = create_activity(
        db_session, slug="python-review", title="Python Review", activity_type="concept_review", skill_ids=["python"]
    )
    baseline = compute_application_priority(
        db_session, application=_application(), job=_JOB, profile=_PROFILE, ranker=TfidfRanker()
    )

    for _ in range(10):
        record_attempt(db_session, activity_id=activity.id, success=True)

    improved = compute_application_priority(
        db_session, application=_application(), job=_JOB, profile=_PROFILE, ranker=TfidfRanker()
    )

    assert improved.score > baseline.score
