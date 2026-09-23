"""CLI: generate a ready-to-paste prompt packet for reviewing a tailored resume with an LLM.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 12 / Checkpoint 6. Copy
the output into an existing Claude or ChatGPT subscription -- no API key,
no automation. Paste the JSON response back with
scripts/apply_ai_resume_review.py.

    python scripts/generate_resume_prompt_packet.py --job-id JOB-001
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from swetrack.domains.jobs.services import list_discovered_job_records
from swetrack.domains.opportunities.config import DataLoadError, load_jobs
from swetrack.domains.opportunities.models import JobRecord
from swetrack.domains.resume.ai_workbench import build_prompt_packet
from swetrack.domains.resume.evidence import DEFAULT_EVIDENCE_PATH, load_evidence_library
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db
from swetrack.infrastructure.paths import find_repo_root

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
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    job = _find_job(args.job_id)
    if job is None:
        raise SystemExit(f"Unknown job id: {args.job_id!r}")

    evidence = load_evidence_library(args.evidence)
    packet = build_prompt_packet(job=job, evidence=evidence)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{_safe_filename(job.job_id)}-prompt.md"
    out_path.write_text(packet, encoding="utf-8")

    print(f"Wrote prompt packet to {out_path}")
    print("Paste its contents into Claude or ChatGPT, then paste the JSON response back with:")
    print(f"  python scripts/apply_ai_resume_review.py --job-id {job.job_id} --response <path-to-response.json>")


if __name__ == "__main__":
    main()
