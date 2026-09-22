"""Render a tailored resume into the original LaTeX template, and compile it to PDF.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 11, steps 7-8: render the
one-page LaTeX resume to PDF; validate page count and text extraction.

The header, Education, and Technical Skills sections are copied verbatim
from the local master_resume.tex (never regenerated) -- only Experience/
Projects section bullets are rebuilt, from selected/reordered evidence, in
plain text (no bold emphasis). ``base_text`` is the truth gate's single
source of truth for what a bullet says; re-deriving bold spans from it
would add a second representation that could drift from it. See the
Checkpoint 5 summary's Known Limitations for the upgrade path.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from swetrack.domains.resume.parser import DraftEntry, escape_latex, parse_entries, parse_sections
from swetrack.domains.resume.schemas import EvidenceItem, SelectedEvidence

LATEX_GENERATOR_VERSION = "latex-v1"

_RENDERED_SECTION_NAMES = {"experience", "projects"}

_COMMON_PDFLATEX_PATHS = (
    "/Library/TeX/texbin/pdflatex",
    "/usr/local/texlive/2026/bin/universal-darwin/pdflatex",
    "/opt/homebrew/bin/pdflatex",
)


def find_pdflatex() -> str | None:
    """Locate a pdflatex executable: PATH first, then common macOS TeX Live install locations."""
    found = shutil.which("pdflatex")
    if found:
        return found
    for candidate in _COMMON_PDFLATEX_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


def _render_entry(entry: DraftEntry, ordered_bullets: list[str]) -> str:
    items = "\n".join(f"    \\item {escape_latex(bullet)}" for bullet in ordered_bullets)
    return f"{entry.raw_header}\\begin{{itemize}}\n{items}\n\\end{{itemize}}\n"


def render_tailored_latex(
    *, master_resume_path: Path, evidence: list[EvidenceItem], selected: list[SelectedEvidence]
) -> str:
    """Rebuild the Experience/Projects sections from selected+reordered evidence.

    Every other section (header, Education, Technical Skills) is copied
    verbatim from ``master_resume_path``. An organization whose every
    bullet was excluded (disabled evidence) is dropped from the rendered
    output entirely, rather than left with an empty bullet list.
    """
    latex = master_resume_path.read_text(encoding="utf-8")
    by_id = {item.id: item for item in evidence}

    ordered_ids_by_org: dict[str, list[str]] = {}
    for entry in selected:
        ordered_ids_by_org.setdefault(by_id[entry.evidence_id].organization, []).append(entry.evidence_id)

    sections = parse_sections(latex)
    rendered_sections: dict[str, str] = {}
    for name, content in sections.items():
        if name.lower() not in _RENDERED_SECTION_NAMES:
            continue
        rebuilt = ""
        for entry in parse_entries(content):
            ordered_ids = ordered_ids_by_org.get(entry.organization, [])
            ordered_bullets = [by_id[eid].base_text for eid in ordered_ids]
            if not ordered_bullets:
                continue
            rebuilt += _render_entry(entry, ordered_bullets)
        rendered_sections[name] = rebuilt

    def _replace_section(match: re.Match[str]) -> str:
        name = match.group(1)
        if name.lower() not in _RENDERED_SECTION_NAMES:
            return match.group(0)
        return f"\\section{{{name}}}\n{rendered_sections.get(name, '')}"

    return re.sub(
        r"\\section\*?\s*\{([^{}]*)\}(.*?)(?=\\section\*?\s*\{|\\end\{document\})",
        _replace_section,
        latex,
        flags=re.S,
    )


@dataclass(frozen=True)
class PdfCompileResult:
    success: bool
    pdf_path: Path | None
    page_count: int | None
    extracted_text: str | None
    log_tail: str
    error: str = ""


def compile_latex_to_pdf(tex_path: Path, *, timeout_seconds: float = 30.0) -> PdfCompileResult:
    """Compile a .tex file to PDF with pdflatex (twice, for stable page layout).

    Returns a result rather than raising: a compile failure is an expected,
    reportable outcome (e.g. a bad character slipping through), not a
    Python exception.
    """
    pdflatex = find_pdflatex()
    if pdflatex is None:
        return PdfCompileResult(
            success=False, pdf_path=None, page_count=None, extracted_text=None, log_tail="", error="pdflatex not found"
        )

    workdir = tex_path.parent
    log_tail = ""
    for _ in range(2):
        try:
            result = subprocess.run(
                [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return PdfCompileResult(
                success=False, pdf_path=None, page_count=None, extracted_text=None, log_tail="", error="pdflatex timed out"
            )
        log_tail = "\n".join(result.stdout.splitlines()[-40:])
        if result.returncode != 0:
            return PdfCompileResult(
                success=False, pdf_path=None, page_count=None, extracted_text=None, log_tail=log_tail, error="pdflatex failed"
            )

    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        return PdfCompileResult(
            success=False, pdf_path=None, page_count=None, extracted_text=None, log_tail=log_tail, error="no PDF produced"
        )

    page_count, extracted_text = _inspect_pdf(pdf_path)
    return PdfCompileResult(
        success=True, pdf_path=pdf_path, page_count=page_count, extracted_text=extracted_text, log_tail=log_tail
    )


def _inspect_pdf(pdf_path: Path) -> tuple[int, str]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return len(reader.pages), text
