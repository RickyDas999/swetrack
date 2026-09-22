"""Parse resume/master_resume.tex into a draft resume/evidence.yaml for your review.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 11: "Parse the current
resume during setup and require the user to approve the initial evidence
library." This is a DRAFT -- read it, fix any mis-split organization/role/
date lines, correct the heuristic skill/metric extraction, and adjust
`verified`/`enabled`/`review_note` before treating it as truth-gate input.

Only Experience and Project bullets become evidence items here: Education
and Technical Skills are copied verbatim into every tailored resume by the
renderer (they are never selected/excluded/reordered), so they do not need
individual evidence records.

    python scripts/parse_resume_to_evidence.py
    python scripts/parse_resume_to_evidence.py --resume resume/master_resume.tex --out resume/evidence.yaml
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from swetrack.domains.resume.parser import DraftEntry, parse_resume, strip_latex_markup
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_RESUME_PATH = find_repo_root() / "resume" / "master_resume.tex"
DEFAULT_EVIDENCE_PATH = find_repo_root() / "resume" / "evidence.yaml"

_SECTION_TO_EVIDENCE_SECTION = {"experience": "experience", "projects": "project"}
_BOLD_SPAN_RE = re.compile(r"\\textbf\{([^{}]*)\}")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "entry"


def _extract_bold_spans(raw_bullet: str) -> list[str]:
    return _BOLD_SPAN_RE.findall(raw_bullet)


def _split_terms(span: str) -> list[str]:
    span = re.sub(r"\band\b", ",", span)
    return [term.strip() for term in span.split(",") if term.strip()]


def _looks_like_metric(span: str) -> bool:
    return bool(re.search(r"\d", span))


def _skills_and_metrics(raw_bullet: str) -> tuple[list[str], list[str]]:
    """Heuristic candidate skills/metrics from a bullet's bold spans -- review before trusting."""
    skills: list[str] = []
    metrics: list[str] = []
    for raw_span in _extract_bold_spans(raw_bullet):
        span = strip_latex_markup(raw_span)
        if not span:
            continue
        if _looks_like_metric(span):
            metrics.append(span)
        else:
            skills.extend(_split_terms(span))
    return skills, metrics


def _entry_evidence_items(section_key: str, entry: DraftEntry, raw_bullets: list[str]) -> list[dict]:
    slug = _slugify(entry.organization)
    items: list[dict] = []
    for index, (bullet, raw_bullet) in enumerate(zip(entry.bullets, raw_bullets), start=1):
        skills, metrics = _skills_and_metrics(raw_bullet)
        items.append(
            {
                "id": f"{slug}-{index}",
                "section": _SECTION_TO_EVIDENCE_SECTION[section_key],
                "organization": entry.organization,
                "role": entry.role_or_skills if section_key == "experience" else "",
                "date_range": entry.date_range,
                "base_text": bullet,
                "supported_skills": sorted(set(skills)),
                "supported_metrics": sorted(set(metrics)),
                "verified": True,
                "enabled": True,
                "review_note": "",
            }
        )
    return items


def _raw_itemize_bullets(section_latex: str) -> list[list[str]]:
    """Re-extract each entry's *raw* (unstripped) \\item bodies, aligned with parse_entries()'s order."""
    per_entry: list[list[str]] = []
    for match in re.finditer(r"\\begin\{itemize\}(.*?)\\end\{itemize\}", section_latex, re.S):
        raw_items = re.findall(r"\\item\s+(.*?)(?=\\item|\Z)", match.group(1), re.S)
        per_entry.append([item for item in raw_items if item.strip()])
    return per_entry


def build_draft_evidence(latex: str) -> list[dict]:
    sections = {name.lower(): content for name, content in _section_contents(latex).items()}
    parsed = parse_resume(latex)

    evidence: list[dict] = []
    for section_name, entries in parsed.items():
        key = section_name.lower()
        if key not in _SECTION_TO_EVIDENCE_SECTION:
            continue
        raw_bullets_per_entry = _raw_itemize_bullets(sections[key])
        for entry, raw_bullets in zip(entries, raw_bullets_per_entry):
            evidence.extend(_entry_evidence_items(key, entry, raw_bullets))
    return evidence


def _section_contents(latex: str) -> dict[str, str]:
    from swetrack.domains.resume.parser import parse_sections

    return parse_sections(latex)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    args = parser.parse_args()

    if not args.resume.exists():
        raise SystemExit(f"Resume file not found: {args.resume}")

    latex = args.resume.read_text(encoding="utf-8")
    evidence = build_draft_evidence(latex)

    with args.out.open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"evidence": evidence}, fh, sort_keys=False, allow_unicode=True, width=100)

    print(f"Wrote {len(evidence)} draft evidence item(s) to {args.out}")
    print("This is a DRAFT -- review every item (especially supported_skills/supported_metrics) before use.")


if __name__ == "__main__":
    main()
