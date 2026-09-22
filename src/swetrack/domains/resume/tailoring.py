"""Deterministic evidence-to-job matching: selection/ordering, gaps, and ATS coverage.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 11's tailoring pipeline,
steps 3-6 (skill matching, bullet selection/reordering, gaps report, ATS
coverage), scoped down for Checkpoint 5:

- Organization/project blocks are never reordered (resumes read
  reverse-chronologically; reordering employers would be misleading).
- Bullets *within* one block are reordered by relevance, never dropped --
  page-length-constrained bullet selection is future work once a
  compile-and-measure feedback loop exists (see latex.py).
- No keyword substitution/wording variants: every included bullet is its
  evidence item's ``base_text`` verbatim. This is a stricter, simpler
  guarantee against fabrication than the handoff's "approved wording
  variants" step, not a partial implementation of it.

Job requirement keywords come only from ``JobRecord.skills`` -- for
Job Radar discovered jobs this is currently empty (no JD skill extraction
yet; see domains/jobs/services.py::to_job_record's Known Limitations), so
gaps/coverage are honestly trivial for those jobs today, not fabricated.
"""

from __future__ import annotations

from swetrack.domains.opportunities.models import JobRecord
from swetrack.domains.resume.schemas import (
    ATSCoverageReport,
    EvidenceItem,
    GapsReport,
    GapsReportEntry,
    ResumeDiff,
    ResumeDiffEntry,
    SelectedEvidence,
)

TAILORING_VERSION = "tailoring-v1"


def _skills_match(a: str, b: str) -> bool:
    """Case-insensitive substring match either direction (mirrors ranking/base.py's _contains_ci)."""
    a_l, b_l = a.strip().lower(), b.strip().lower()
    return bool(a_l) and bool(b_l) and (a_l in b_l or b_l in a_l)


def extract_job_requirements(job: JobRecord) -> list[str]:
    """The job's required/preferred skill keywords. See module docstring for the discovered-job caveat."""
    return list(job.skills)


def _score_item(item: EvidenceItem, job_skills: list[str]) -> tuple[int, list[str]]:
    matched = [skill for skill in job_skills if any(_skills_match(s, skill) for s in item.supported_skills)]
    return len(matched), matched


def select_and_order_evidence(job: JobRecord, evidence: list[EvidenceItem]) -> list[SelectedEvidence]:
    """Every enabled evidence item, grouped by (section, organization) in first-seen order,
    with bullets *within* each group sorted by descending relevance to this job."""
    job_skills = extract_job_requirements(job)
    enabled = [item for item in evidence if item.enabled]

    groups: dict[tuple[str, str], list[EvidenceItem]] = {}
    group_order: list[tuple[str, str]] = []
    for item in enabled:
        key = (item.section, item.organization)
        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append(item)

    selected: list[SelectedEvidence] = []
    for key in group_order:
        items = groups[key]
        scored = [(*_score_item(item, job_skills), item) for item in items]
        scored.sort(key=lambda triple: (-triple[0], items.index(triple[2])))
        for score, matched, item in scored:
            selected.append(SelectedEvidence(evidence_id=item.id, relevance_score=float(score), matched_skills=matched))
    return selected


def compute_gaps(job: JobRecord, evidence: list[EvidenceItem]) -> GapsReport:
    """Job-required skills with no supporting (enabled) evidence anywhere in the library.

    CLAUDE.md: "Missing job requirements belong in a gaps report, not in
    the resume" -- these skills are never added to a tailored resume.
    """
    job_skills = extract_job_requirements(job)
    enabled = [item for item in evidence if item.enabled]

    gaps = [
        GapsReportEntry(skill=skill)
        for skill in job_skills
        if not any(any(_skills_match(s, skill) for s in item.supported_skills) for item in enabled)
    ]
    return GapsReport(job_id=job.job_id, gaps=gaps)


def compute_ats_coverage(job: JobRecord, evidence: list[EvidenceItem]) -> ATSCoverageReport:
    """Transparent keyword coverage -- never an "ATS pass probability" (CLAUDE.md)."""
    job_skills = extract_job_requirements(job)
    enabled = [item for item in evidence if item.enabled]
    all_supported_skills = sorted({skill for item in enabled for skill in item.supported_skills})

    covered = [
        skill for skill in job_skills if any(any(_skills_match(s, skill) for s in item.supported_skills) for item in enabled)
    ]
    unsupported = [skill for skill in job_skills if skill not in covered]
    unused = [
        skill
        for skill in all_supported_skills
        if not any(_skills_match(skill, job_skill) for job_skill in job_skills)
    ]

    return ATSCoverageReport(
        job_id=job.job_id,
        covered_keywords=covered,
        supported_but_unused_keywords=unused,
        unsupported_keywords=unsupported,
    )


def compute_diff(job: JobRecord, evidence: list[EvidenceItem], selected: list[SelectedEvidence]) -> ResumeDiff:
    """What changed between the full base resume (every enabled item, base order) and this tailoring pass.

    Selection/reordering only -- CLAUDE.md: "Never alter dates, titles,
    employers, metrics, scale, or deployment status without approved
    evidence," so no entry here ever represents a text change.
    """
    base_order = [item.id for item in evidence if item.enabled]
    selected_order = [entry.evidence_id for entry in selected]

    entries: list[ResumeDiffEntry] = []
    for item in evidence:
        if item.id not in selected_order:
            change = "excluded"
        elif base_order.index(item.id) == selected_order.index(item.id):
            change = "kept"
        else:
            change = "reordered"
        entries.append(ResumeDiffEntry(evidence_id=item.id, organization=item.organization, change=change))

    return ResumeDiff(job_id=job.job_id, entries=entries)
