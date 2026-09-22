"""Evidence-to-job matching: selection/ordering, gaps, and ATS coverage (synthetic data only)."""

from __future__ import annotations

from swetrack.domains.opportunities.models import JobRecord
from swetrack.domains.resume.schemas import EvidenceItem
from swetrack.domains.resume.tailoring import (
    compute_ats_coverage,
    compute_diff,
    compute_gaps,
    select_and_order_evidence,
)

_EVIDENCE = [
    EvidenceItem(
        id="fakeco-1",
        section="experience",
        organization="Fake Co",
        role="Intern",
        date_range="2025",
        base_text="Built a Python and AWS Lambda pipeline.",
        supported_skills=["Python", "AWS Lambda"],
    ),
    EvidenceItem(
        id="fakeco-2",
        section="experience",
        organization="Fake Co",
        role="Intern",
        date_range="2025",
        base_text="Wrote SQL reports.",
        supported_skills=["SQL"],
    ),
    EvidenceItem(
        id="otherco-1",
        section="experience",
        organization="Other Co",
        role="Founder",
        date_range="2020",
        base_text="Ran a nonprofit.",
        supported_skills=["Leadership"],
    ),
    EvidenceItem(
        id="disabled-1",
        section="project",
        organization="Disabled Project",
        role="",
        date_range="",
        base_text="Claims something unverified.",
        supported_skills=["React"],
        verified=False,
        enabled=False,
    ),
]


def _job(skills: list[str]) -> JobRecord:
    return JobRecord(job_id="JOB-1", company="Target Co", title="SWE", skills=skills, source="synthetic")


def test_select_and_order_prioritizes_matching_bullets_within_an_organization() -> None:
    selected = select_and_order_evidence(_job(["Python", "AWS Lambda"]), _EVIDENCE)
    fakeco_ids = [s.evidence_id for s in selected if s.evidence_id.startswith("fakeco")]
    assert fakeco_ids == ["fakeco-1", "fakeco-2"]  # fakeco-1 matches 2 skills, fakeco-2 matches 0


def test_select_and_order_preserves_organization_order() -> None:
    selected = select_and_order_evidence(_job([]), _EVIDENCE)
    organizations_in_order = []
    for entry in selected:
        item = next(e for e in _EVIDENCE if e.id == entry.evidence_id)
        if item.organization not in organizations_in_order:
            organizations_in_order.append(item.organization)
    assert organizations_in_order == ["Fake Co", "Other Co"]  # never "Disabled Project" -- excluded


def test_select_and_order_excludes_disabled_evidence() -> None:
    selected = select_and_order_evidence(_job(["React"]), _EVIDENCE)
    assert all(entry.evidence_id != "disabled-1" for entry in selected)


def test_compute_gaps_flags_unsupported_job_skills() -> None:
    gaps = compute_gaps(_job(["Python", "Kubernetes"]), _EVIDENCE)
    assert [g.skill for g in gaps.gaps] == ["Kubernetes"]


def test_compute_gaps_does_not_flag_skills_only_disabled_evidence_supports() -> None:
    # "React" is only supported by the disabled/unverified evidence item --
    # it must still show as a gap, not be silently considered "covered."
    gaps = compute_gaps(_job(["React"]), _EVIDENCE)
    assert [g.skill for g in gaps.gaps] == ["React"]


def test_compute_ats_coverage_separates_covered_and_unsupported() -> None:
    report = compute_ats_coverage(_job(["Python", "Kubernetes"]), _EVIDENCE)
    assert report.covered_keywords == ["Python"]
    assert report.unsupported_keywords == ["Kubernetes"]
    assert "SQL" in report.supported_but_unused_keywords


def test_compute_diff_flags_reordered_and_excluded_evidence() -> None:
    job = _job(["SQL"])  # makes fakeco-2 outrank fakeco-1 within Fake Co
    selected = select_and_order_evidence(job, _EVIDENCE)
    diff = compute_diff(job, _EVIDENCE, selected)

    by_id = {entry.evidence_id: entry.change for entry in diff.entries}
    assert by_id["fakeco-2"] == "reordered"  # moved ahead of fakeco-1
    assert by_id["disabled-1"] == "excluded"  # never enabled in the first place


def test_compute_diff_flags_kept_when_no_job_skills_change_order() -> None:
    job = _job([])
    selected = select_and_order_evidence(job, _EVIDENCE)
    diff = compute_diff(job, _EVIDENCE, selected)

    by_id = {entry.evidence_id: entry.change for entry in diff.entries}
    assert by_id["fakeco-1"] == "kept"
    assert by_id["fakeco-2"] == "kept"
