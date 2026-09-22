"""Deterministic new-grad eligibility classification (Job Radar Checkpoint 3)."""

from __future__ import annotations

from swetrack.domains.jobs.eligibility import classify_new_grad_eligibility
from swetrack.domains.jobs.schemas import CandidateEligibilityProfile

_CANDIDATE = CandidateEligibilityProfile(
    name="Test Candidate",
    graduation_year=2026,
    graduation_month=5,
    excluded_levels=["Senior", "Staff", "Principal", "Manager", "Director", "Lead"],
)


def test_clear_new_grad_title_and_description_is_eligible() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer, New Grad 2026",
        description="We welcome entry level candidates and recent graduates. 0-2 years experience.",
        candidate=_CANDIDATE,
    )
    assert result.status == "eligible"
    assert result.confidence > 0.5
    assert "new grad" in result.positive_signals
    assert not result.negative_signals


def test_senior_title_is_ineligible() -> None:
    result = classify_new_grad_eligibility(
        title="Senior Software Engineer",
        description="10+ years of experience required.",
        candidate=_CANDIDATE,
    )
    assert result.status == "ineligible"
    assert "senior" in result.negative_signals
    assert "10+ years experience required" in result.negative_signals


def test_senior_mentioned_only_in_body_does_not_disqualify() -> None:
    # Title-only excluded-level check: a body mention like "work alongside
    # senior engineers" should not disqualify a genuinely junior posting.
    result = classify_new_grad_eligibility(
        title="Software Engineer, New Grad",
        description="You'll work alongside senior engineers on our platform team.",
        candidate=_CANDIDATE,
    )
    assert "senior" not in result.negative_signals


def test_internship_title_is_ineligible() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineering Intern",
        description="Summer internship program.",
        candidate=_CANDIDATE,
    )
    assert result.status == "ineligible"
    assert "internship/co-op title" in result.negative_signals


def test_conflicting_signals_are_uncertain_not_ineligible() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer",
        description="0-2 years experience preferred, but 10+ years experience required for senior scope.",
        candidate=_CANDIDATE,
    )
    assert result.status == "uncertain"
    assert result.positive_signals
    assert result.negative_signals


def test_no_signals_at_all_is_uncertain_not_rejected() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer",
        description="Build and maintain backend services.",
        candidate=_CANDIDATE,
    )
    assert result.status == "uncertain"
    assert not result.negative_signals


def test_graduation_year_phrase_is_a_positive_signal() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer",
        description="Open to Class of 2026 graduates.",
        candidate=_CANDIDATE,
    )
    assert "class of 2026" in result.positive_signals
    assert result.status == "eligible"


def test_different_graduation_year_does_not_match() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer",
        description="Open to Class of 2025 graduates only.",
        candidate=_CANDIDATE,
    )
    assert "class of 2026" not in result.positive_signals


def test_security_clearance_is_a_negative_signal() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer, New Grad",
        description="Active security clearance required.",
        candidate=_CANDIDATE,
    )
    assert "security clearance required" in result.negative_signals


def test_excessive_experience_requirement_is_ineligible() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer",
        description="Minimum 5 years experience required.",
        candidate=_CANDIDATE,
    )
    assert result.status == "ineligible"


def test_closed_posting_text_is_a_negative_signal() -> None:
    result = classify_new_grad_eligibility(
        title="Software Engineer, New Grad",
        description="This position has been filled.",
        candidate=_CANDIDATE,
    )
    assert "posting indicates it is closed/filled" in result.negative_signals


def test_excluded_levels_default_when_candidate_list_is_empty() -> None:
    candidate = CandidateEligibilityProfile(name="Test", graduation_year=2026, excluded_levels=[])
    result = classify_new_grad_eligibility(title="Staff Software Engineer", description="", candidate=candidate)
    assert "staff" in result.negative_signals
