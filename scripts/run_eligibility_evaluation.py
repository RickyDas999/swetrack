"""Evaluate the deterministic new-grad eligibility classifier against a labeled fixture.

Job Radar Checkpoint 3 acceptance: "Evaluation command prints precision,
recall, F1, and confusion matrix." data/eligibility_labels.csv is a
reviewed, hand-labeled fixture (30 examples across true new-grad SWE,
generic entry-level, internships, senior/lead roles, adjacent technical
roles, ambiguous/conflicting experience requirements, and duplicate
cross-postings -- SWETrack_Job_Radar_Claude_Code_Handoff.md Section 17),
not scraped or real usage data.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from swetrack.domains.jobs.candidate_config import load_candidate_eligibility_profile
from swetrack.infrastructure.paths import find_repo_root
from swetrack.ml.evaluation.eligibility import LabeledJob, evaluate_eligibility_classifier

DEFAULT_LABELS_PATH = find_repo_root() / "data" / "eligibility_labels.csv"


def load_labeled_jobs(path: Path) -> list[LabeledJob]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [
            {
                "job_id": row["job_id"],
                "title": row["title"],
                "description": row["description"],
                "true_status": row["true_status"],
            }
            for row in reader
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_PATH)
    args = parser.parse_args()

    labeled_jobs = load_labeled_jobs(args.labels)
    candidate = load_candidate_eligibility_profile()
    result = evaluate_eligibility_classifier(labeled_jobs, candidate)

    print(f"Reviewed, hand-labeled fixture -- {result['n_evaluated']} jobs. Not scraped or real usage data.\n")
    print(result["classification_report"])

    labels = result["labels"]
    print("Confusion matrix (rows=true label, columns=predicted):")
    print(f"{'':>12}" + "".join(f"{label:>12}" for label in labels))
    for true_label, row in zip(labels, result["confusion_matrix"]):
        print(f"{true_label:>12}" + "".join(f"{count:>12}" for count in row))

    misses = [
        (job["job_id"], job["title"], job["true_status"], prediction)
        for job, prediction in zip(labeled_jobs, result["predictions"])
        if prediction != job["true_status"]
    ]
    if misses:
        print(f"\n{len(misses)} misclassified example(s):")
        for job_id, title, true_status, predicted in misses:
            print(f"  {job_id} {title!r}: true={true_status} predicted={predicted}")
    else:
        print("\nNo misclassifications on this fixture.")


if __name__ == "__main__":
    main()
