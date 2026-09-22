"""CLI: generate a truth-gated, evidence-backed tailored resume for one job.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 11's tailoring pipeline
output: selected/reordered evidence, a gaps report, an ATS coverage report,
and (if pdflatex is available) a compiled, validated PDF.

    python scripts/tailor_resume.py --job-id JOB-003
    python scripts/tailor_resume.py --job-id "greenhouse:123" --out-dir resume/variants
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from swetrack.domains.jobs.services import list_discovered_job_records
from swetrack.domains.opportunities.config import DataLoadError, load_jobs
from swetrack.domains.opportunities.models import JobRecord
from swetrack.domains.resume.evidence import DEFAULT_EVIDENCE_PATH, load_evidence_library
from swetrack.domains.resume.latex import compile_latex_to_pdf, find_pdflatex, render_tailored_latex
from swetrack.domains.resume.tailoring import compute_ats_coverage, compute_gaps, select_and_order_evidence
from swetrack.domains.resume.truth_gate import validate_selection
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_MASTER_RESUME_PATH = find_repo_root() / "resume" / "master_resume.tex"
DEFAULT_OUT_DIR = find_repo_root() / "resume" / "variants"


def _find_job(job_id: str) -> JobRecord | None:
    try:
        sample_jobs = load_jobs()
    except DataLoadError:
        sample_jobs = []
    match = next((job for job in sample_jobs if job.job_id == job_id), None)
    if match is not None:
        return match

    engine = get_engine()
    init_db(engine)
    session = get_sessionmaker(engine)()
    try:
        discovered = list_discovered_job_records(session)
    finally:
        session.close()
    return next((job for job in discovered if job.job_id == job_id), None)


def _safe_filename(job_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", job_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--job-id", required=True, help="A sample-CSV job_id or a discovered job's canonical_key")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--resume", type=Path, default=DEFAULT_MASTER_RESUME_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    job = _find_job(args.job_id)
    if job is None:
        raise SystemExit(f"Unknown job id: {args.job_id!r}")

    if not args.resume.exists():
        raise SystemExit(
            f"Resume file not found: {args.resume}\n"
            "This file is gitignored (contains personal contact info) -- place your real "
            "resume there, or pass --resume to point at another copy."
        )

    evidence = load_evidence_library(args.evidence)
    selected = select_and_order_evidence(job, evidence)

    violations = validate_selection(selected, evidence)
    if violations:
        for violation in violations:
            print(f"TRUTH GATE VIOLATION: {violation.evidence_id}: {violation.reason}")
        raise SystemExit("Truth gate failed -- no resume generated.")

    gaps = compute_gaps(job, evidence)
    coverage = compute_ats_coverage(job, evidence)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = args.out_dir / f"{_safe_filename(job.job_id)}.tex"
    rendered = render_tailored_latex(master_resume_path=args.resume, evidence=evidence, selected=selected)
    tex_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote tailored LaTeX to {tex_path}")

    print(f"\nGaps ({len(gaps.gaps)}) -- never added to the resume:")
    for gap in gaps.gaps:
        print(f"  - {gap.skill}")

    print(f"\nATS coverage: {len(coverage.covered_keywords)} covered, {len(coverage.unsupported_keywords)} unsupported")
    print(f"  covered:     {coverage.covered_keywords}")
    print(f"  unsupported: {coverage.unsupported_keywords}")

    if find_pdflatex() is None:
        print("\npdflatex not found -- skipping PDF compilation.")
        return

    result = compile_latex_to_pdf(tex_path)
    if not result.success:
        print(f"\nPDF compilation FAILED: {result.error}\n{result.log_tail}")
        raise SystemExit(1)

    print(f"\nCompiled PDF: {result.pdf_path} ({result.page_count} page(s))")
    if result.page_count != 1:
        print("WARNING: resume is not exactly one page.")


if __name__ == "__main__":
    main()
