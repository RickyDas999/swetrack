"""Evaluation harness for the deterministic new-grad eligibility classifier.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 17 / Checkpoint 3
acceptance: "Evaluation command prints precision, recall, F1, and confusion
matrix." Uses scikit-learn's existing metrics (already a project
dependency) rather than hand-rolling them.
"""

from __future__ import annotations

from typing import TypedDict

from sklearn.metrics import classification_report, confusion_matrix

from swetrack.domains.jobs.eligibility import EligibilityStatus, classify_new_grad_eligibility
from swetrack.domains.jobs.schemas import CandidateEligibilityProfile

_LABELS: list[EligibilityStatus] = ["eligible", "uncertain", "ineligible"]


class LabeledJob(TypedDict):
    job_id: str
    title: str
    description: str
    true_status: EligibilityStatus


class EligibilityEvaluationResult(TypedDict):
    n_evaluated: int
    predictions: list[EligibilityStatus]
    truths: list[EligibilityStatus]
    classification_report: str
    confusion_matrix: list[list[int]]
    labels: list[EligibilityStatus]


def evaluate_eligibility_classifier(
    labeled_jobs: list[LabeledJob], candidate: CandidateEligibilityProfile
) -> EligibilityEvaluationResult:
    """Run the classifier over every labeled job and score it against the reviewed true labels."""
    if not labeled_jobs:
        raise ValueError("Need at least one labeled job to evaluate")

    truths: list[EligibilityStatus] = []
    predictions: list[EligibilityStatus] = []
    for job in labeled_jobs:
        assessment = classify_new_grad_eligibility(
            title=job["title"], description=job["description"], candidate=candidate
        )
        predictions.append(assessment.status)
        truths.append(job["true_status"])

    report = classification_report(truths, predictions, labels=_LABELS, zero_division=0)
    matrix = confusion_matrix(truths, predictions, labels=_LABELS)

    return {
        "n_evaluated": len(labeled_jobs),
        "predictions": predictions,
        "truths": truths,
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "labels": _LABELS,
    }
