"""Resume LaTeX parser tests, against synthetic fixture data (never a real resume)."""

from __future__ import annotations

from swetrack.domains.resume.parser import (
    escape_latex,
    find_command_args,
    parse_resume,
    parse_sections,
    strip_latex_markup,
)

_SYNTHETIC_RESUME = r"""
\documentclass[letterpaper,10pt]{article}
\begin{document}
\begin{center}
    {\LARGE \textbf{Jordan Example}} \\[2pt]
    (555)-000-0000 \;|\; \href{mailto:jordan@example.com}{jordan@example.com}
\end{center}

\section{Education}
\textbf{Example University}, Graduate \hfill Example City, XX \\
\textbf{Major:} \textit{B.S. in Computer Science} \hfill \textit{Sep. 2022 -- May 2026} \\

\section{Experience}
\textbf{Fake Company} \hfill Remote \\
\textit{Software Engineering Intern \textbf{--} Platform Team} \hfill May 2025 \textbf{--} Aug. 2025
\begin{itemize}
    \item Built a \textbf{data pipeline} using \textbf{Python and AWS Lambda} processing \textbf{10K+ events} daily.
    \item Reduced \textbf{latency by 40\%} through caching improvements.
\end{itemize}

\section{Projects}
\textbf{Widget Tracker \textbf{--} Personal Project} \;|\; \textit{Python, FastAPI, SQLite}
\begin{itemize}
\item Built a \textbf{full-stack app} tracking widgets with a \textbf{FastAPI} backend.
\end{itemize}

\section{Technical Skills}
\textbf{Languages:} Python, Java \\

\end{document}
"""


def test_strip_latex_markup_unwraps_nested_commands() -> None:
    result = strip_latex_markup(r"Software Engineering Intern \textbf{--} Platform Team")
    assert result == "Software Engineering Intern -- Platform Team"


def test_strip_latex_markup_handles_escaped_symbols() -> None:
    assert strip_latex_markup(r"Reduced \textbf{latency by 40\%}") == "Reduced latency by 40%"


def test_find_command_args_handles_nested_braces() -> None:
    text = r"\textbf{SWETrack \textbf{--} SWE Recruiting Platform}"
    args = find_command_args(text, "textbf")
    assert len(args) == 1
    assert args[0] == r"SWETrack \textbf{--} SWE Recruiting Platform"


def test_parse_sections_finds_all_section_names() -> None:
    sections = parse_sections(_SYNTHETIC_RESUME)
    assert set(sections.keys()) == {"Education", "Experience", "Projects", "Technical Skills"}


def test_parse_entries_extracts_organization_role_and_dates() -> None:
    parsed = parse_resume(_SYNTHETIC_RESUME)
    experience = parsed["Experience"]
    assert len(experience) == 1

    entry = experience[0]
    assert entry.organization == "Fake Company"
    assert entry.role_or_skills == "Software Engineering Intern -- Platform Team"
    assert entry.date_range == "May 2025 -- Aug. 2025"
    assert len(entry.bullets) == 2
    assert "data pipeline" in entry.bullets[0]
    assert "10K+ events" in entry.bullets[0]
    assert "40%" in entry.bullets[1]


def test_parse_entries_handles_project_style_header_with_skill_list() -> None:
    parsed = parse_resume(_SYNTHETIC_RESUME)
    projects = parsed["Projects"]
    assert len(projects) == 1

    entry = projects[0]
    assert entry.organization == "Widget Tracker -- Personal Project"
    assert entry.role_or_skills == "Python, FastAPI, SQLite"
    assert entry.date_range == ""  # no \hfill in this header style
    assert len(entry.bullets) == 1


def test_parse_resume_skips_sections_with_no_itemize_blocks() -> None:
    parsed = parse_resume(_SYNTHETIC_RESUME)
    assert parsed["Education"] == []
    assert parsed["Technical Skills"] == []


def test_escape_latex_handles_dollar_percent_and_ampersand() -> None:
    # Regression: a bare "$" toggles LaTeX math mode and corrupts the
    # document ("\item invalid in math mode") if not re-escaped before
    # being embedded back into rendered .tex source.
    assert escape_latex("Saved $18K+ (80% faster) for R&D") == r"Saved \$18K+ (80\% faster) for R\&D"


def test_escape_latex_round_trips_with_strip_latex_markup() -> None:
    original = r"Saved \$18K+ and \%80 improvement"
    plain = strip_latex_markup(original)
    assert plain == "Saved $18K+ and %80 improvement"
    assert escape_latex(plain) == r"Saved \$18K+ and \%80 improvement"
