"""CLI: validate a pasted-back AI resume review, and render/compile it if it passes the truth gate.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 12 / Checkpoint 6.
Everything the AI proposed is checked against the same truth gate a
deterministic tailoring pass uses (scripts/tailor_resume.py) -- an
unknown, disabled, or unverified evidence id is rejected with a specific
reason, never silently applied.

    python scripts/apply_ai_resume_review.py --job-id JOB-001 --response resume/variants/JOB-001-response.json
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from swetrack.domains.jobs.services import list_discovered_job_records
from swetrack.domains.opportunities.config import DataLoadError, load_jobs
from swetrack.domains.opportunities.models import JobRecord
from swetrack.domains.resume.ai_workbench import parse_ai_response, validate_ai_response
from swetrack.domains.resume.evidence import DEFAULT_EVIDENCE_PATH, load_evidence_library
from swetrack.domains.resume.latex import compile_latex_to_pdf, find_pdflatex, render_tailored_latex
from swetrack.domains.resume.schemas import SelectedEvidence
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
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--response", type=Path, required=True, help="Path to the pasted-back JSON response")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--resume", type=Path, default=DEFAULT_MASTER_RESUME_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    job = _find_job(args.job_id)
    if job is None:
        raise SystemExit(f"Unknown job id: {args.job_id!r}")

    if not args.response.exists():
        raise SystemExit(f"Response file not found: {args.response}")

    evidence = load_evidence_library(args.evidence)

    try:
        response = parse_ai_response(args.response.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit(f"Could not parse AI response: {exc}") from exc

    result = validate_ai_response(response, job=job, evidence=evidence)
    if not result.accepted:
        print("AI response REJECTED by the truth gate:")
        for violation in result.violations:
            print(f"  - {violation.evidence_id}: {violation.reason}")
        raise SystemExit(1)

    print("AI response accepted. Diff vs. the full base resume:")
    for entry in result.diff.entries:
        print(f"  {entry.change:>9}  {entry.evidence_id} ({entry.organization})")
    if response.notes:
        print(f"\nAI notes: {response.notes}")

    if not args.resume.exists():
        raise SystemExit(f"\nResume file not found: {args.resume} -- cannot render (nothing else to do).")

    selected = [
        SelectedEvidence(evidence_id=eid, relevance_score=0.0, matched_skills=[])
        for eid in dict.fromkeys(response.recommended_evidence_ids)
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = args.out_dir / f"{_safe_filename(job.job_id)}-ai-reviewed.tex"
    rendered = render_tailored_latex(master_resume_path=args.resume, evidence=evidence, selected=selected)
    tex_path.write_text(rendered, encoding="utf-8")
    print(f"\nWrote AI-reviewed LaTeX to {tex_path}")

    if find_pdflatex() is None:
        print("pdflatex not found -- skipping PDF compilation.")
        return

    compile_result = compile_latex_to_pdf(tex_path)
    if not compile_result.success:
        print(f"PDF compilation FAILED: {compile_result.error}\n{compile_result.log_tail}")
        raise SystemExit(1)

    print(f"Compiled PDF: {compile_result.pdf_path} ({compile_result.page_count} page(s))")
    if compile_result.page_count != 1:
        print("WARNING: resume is not exactly one page.")


if __name__ == "__main__":
    main()
