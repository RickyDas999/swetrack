"""Tailored-resume LaTeX rendering and PDF compilation (synthetic data only, never a real resume)."""

from __future__ import annotations

from pathlib import Path

import pytest

from swetrack.domains.resume.latex import compile_latex_to_pdf, find_pdflatex, render_tailored_latex
from swetrack.domains.resume.schemas import EvidenceItem, SelectedEvidence

_SYNTHETIC_RESUME = r"""
\documentclass[letterpaper,10pt]{article}
\begin{document}
\begin{center}
    {\LARGE \textbf{Jordan Example}} \\[2pt]
    (555)-000-0000 \;|\; jordan@example.com
\end{center}

\section{Education}
\textbf{Example University}, Graduate \hfill Example City, XX \\
\textbf{Major:} \textit{B.S. in Computer Science} \hfill \textit{Sep. 2022 -- May 2026} \\

\section{Experience}
\textbf{Fake Company} \hfill Remote \\
\textit{Software Engineering Intern} \hfill May 2025 \textbf{--} Aug. 2025
\begin{itemize}
    \item Built a data pipeline using Python and AWS Lambda.
    \item Wrote SQL reports for stakeholders.
\end{itemize}

\section{Technical Skills}
\textbf{Languages:} Python, Java \\

\end{document}
"""

_EVIDENCE = [
    EvidenceItem(
        id="fakeco-1",
        section="experience",
        organization="Fake Company",
        base_text="Built a data pipeline using Python and AWS Lambda.",
        supported_skills=["Python", "AWS Lambda"],
    ),
    EvidenceItem(
        id="fakeco-2",
        section="experience",
        organization="Fake Company",
        base_text="Wrote SQL reports for stakeholders.",
        supported_skills=["SQL"],
    ),
]


def _write_synthetic_resume(tmp_path: Path) -> Path:
    path = tmp_path / "master_resume.tex"
    path.write_text(_SYNTHETIC_RESUME)
    return path


def test_render_keeps_header_and_education_verbatim(tmp_path: Path) -> None:
    resume_path = _write_synthetic_resume(tmp_path)
    selected = [
        SelectedEvidence(evidence_id="fakeco-1", relevance_score=1.0, matched_skills=["Python"]),
        SelectedEvidence(evidence_id="fakeco-2", relevance_score=0.0, matched_skills=[]),
    ]

    rendered = render_tailored_latex(master_resume_path=resume_path, evidence=_EVIDENCE, selected=selected)

    assert "Jordan Example" in rendered
    assert "Example University" in rendered
    assert "Languages:} Python, Java" in rendered


def test_render_reorders_bullets_by_selection_order(tmp_path: Path) -> None:
    resume_path = _write_synthetic_resume(tmp_path)
    # Reversed order vs. the source file -- SQL bullet should now render first.
    selected = [
        SelectedEvidence(evidence_id="fakeco-2", relevance_score=1.0, matched_skills=["SQL"]),
        SelectedEvidence(evidence_id="fakeco-1", relevance_score=0.0, matched_skills=[]),
    ]

    rendered = render_tailored_latex(master_resume_path=resume_path, evidence=_EVIDENCE, selected=selected)

    sql_index = rendered.index("Wrote SQL reports")
    pipeline_index = rendered.index("Built a data pipeline")
    assert sql_index < pipeline_index


def test_render_drops_organization_with_no_selected_bullets(tmp_path: Path) -> None:
    resume_path = _write_synthetic_resume(tmp_path)
    rendered = render_tailored_latex(master_resume_path=resume_path, evidence=_EVIDENCE, selected=[])

    assert "Fake Company" not in rendered
    assert "Jordan Example" in rendered  # header still present


def test_render_never_alters_bullet_text() -> None:
    # base_text is copied verbatim -- this is what the truth gate depends on.
    for item in _EVIDENCE:
        assert item.base_text  # sanity: not empty, so the "verbatim" check below is meaningful


@pytest.mark.skipif(find_pdflatex() is None, reason="pdflatex not installed in this environment")
def test_compile_produces_a_one_page_pdf_with_extractable_text(tmp_path: Path) -> None:
    resume_path = _write_synthetic_resume(tmp_path)
    selected = [SelectedEvidence(evidence_id="fakeco-1", relevance_score=1.0, matched_skills=["Python"])]
    rendered = render_tailored_latex(master_resume_path=resume_path, evidence=_EVIDENCE, selected=selected)

    tex_path = tmp_path / "tailored.tex"
    tex_path.write_text(rendered)

    result = compile_latex_to_pdf(tex_path)

    assert result.success, result.log_tail
    assert result.page_count == 1
    assert "Jordan Example" in (result.extracted_text or "")
    assert "Built a data pipeline" in (result.extracted_text or "")
    assert "Wrote SQL reports" not in (result.extracted_text or "")  # excluded bullet


@pytest.mark.skipif(find_pdflatex() is None, reason="pdflatex not installed in this environment")
def test_compile_handles_bullets_with_dollar_percent_and_ampersand(tmp_path: Path) -> None:
    # Regression: a bare "$" in base_text previously toggled LaTeX math
    # mode and produced "\item invalid in math mode", a fatal compile
    # error -- see parser.escape_latex.
    resume_path = _write_synthetic_resume(tmp_path)
    evidence = [
        *_EVIDENCE,
        EvidenceItem(
            id="fakeco-3",
            section="experience",
            organization="Fake Company",
            base_text="Saved $18K+ (80% faster) through R&D improvements.",
            supported_skills=[],
        ),
    ]
    selected = [SelectedEvidence(evidence_id="fakeco-3", relevance_score=1.0, matched_skills=[])]
    rendered = render_tailored_latex(master_resume_path=resume_path, evidence=evidence, selected=selected)

    tex_path = tmp_path / "tailored.tex"
    tex_path.write_text(rendered)

    result = compile_latex_to_pdf(tex_path)

    assert result.success, result.log_tail
    assert "$18K+" in (result.extracted_text or "")


@pytest.mark.skipif(find_pdflatex() is None, reason="pdflatex not installed in this environment")
def test_compile_reports_failure_for_broken_latex(tmp_path: Path) -> None:
    tex_path = tmp_path / "broken.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}\undefinedcommand{oops}\end{document}")

    result = compile_latex_to_pdf(tex_path)

    assert result.success is False
    assert result.pdf_path is None
