"""Tests for the eligibility classifier evaluation harness (Job Radar Checkpoint 3)."""

from __future__ import annotations

import pytest

from swetrack.domains.jobs.schemas import CandidateEligibilityProfile
from swetrack.ml.evaluation.eligibility import evaluate_eligibility_classifier

_CANDIDATE = CandidateEligibilityProfile(name="Test Candidate", graduation_year=2026)


def test_evaluate_reports_perfect_accuracy_on_unambiguous_examples() -> None:
    labeled_jobs = [
        {
            "job_id": "1",
            "title": "Software Engineer, New Grad",
            "description": "Entry level role for recent graduates.",
            "true_status": "eligible",
        },
        {
            "job_id": "2",
            "title": "Senior Software Engineer",
            "description": "10+ years of experience required.",
            "true_status": "ineligible",
        },
    ]

    result = evaluate_eligibility_classifier(labeled_jobs, _CANDIDATE)

    assert result["n_evaluated"] == 2
    assert result["predictions"] == ["eligible", "ineligible"]
    assert "precision" in result["classification_report"]
    assert len(result["confusion_matrix"]) == 3  # eligible/uncertain/ineligible, fixed label order


def test_evaluate_requires_at_least_one_labeled_job() -> None:
    with pytest.raises(ValueError):
        evaluate_eligibility_classifier([], _CANDIDATE)
