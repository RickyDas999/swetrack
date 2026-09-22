"""Heuristic LaTeX resume parser: draft evidence extraction, not a general LaTeX engine.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 11: "Parse the current
resume during setup and require the user to approve the initial evidence
library." This targets this project's own resume template's conventions
specifically (``\\section{...}``, ``\\textbf{Org} \\hfill Location \\\\``,
``\\textit{Role} \\hfill Dates``, ``\\begin{itemize}...\\end{itemize}``) --
not arbitrary LaTeX. Output is a *draft* for human review, not a
blindly-trusted final evidence library: a parser this targeted will
sometimes mis-split an org/role/date line, and that is expected and fine.

The one genuinely reusable piece is ``_extract_command_arg``, a proper
balanced-brace matcher: this resume template nests commands inside each
other (``\\textit{Role \\textbf{--} More role}``), which a naive
``\\textbf\\{([^{}]*)\\}``-style regex cannot handle correctly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STRIP_COMMAND_RE = re.compile(r"\\(?:textbf|textit|text|emph)\s*\{([^{}]*)\}")
_BARE_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")

_LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "^": r"\textasciicircum{}",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "%": r"\%",
}


@dataclass
class DraftEntry:
    """One organization/project block: a header plus its bullets.

    ``raw_header`` is the header's *unstripped* LaTeX (org/location/role/
    dates with all original formatting intact) -- the renderer reuses it
    verbatim so a tailored resume's header lines are never reconstructed
    from scratch, only its ``\\item`` bullets are rebuilt from evidence.
    """

    organization: str
    role_or_skills: str
    date_range: str
    raw_header: str = ""
    bullets: list[str] = field(default_factory=list)


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text before embedding it back into a .tex file.

    The inverse of ``strip_latex_markup``: evidence.yaml stores human-
    readable plain text (``$18K+``, not ``\\$18K+``), so the renderer must
    re-escape it here or a bare ``$``/``%``/``&`` would corrupt the
    document (``$`` toggles math mode, etc.) -- exactly the
    ``\\item invalid in math mode`` failure this exists to prevent.
    """
    return "".join(_LATEX_SPECIAL_CHARS.get(ch, ch) for ch in text)


def strip_latex_markup(text: str) -> str:
    """Best-effort LaTeX -> plain text for one resume line or bullet.

    Iterates command-unwrapping to convergence so nested commands (e.g.
    ``\\textit{...\\textbf{--}...}``) resolve from the inside out. Escaped
    symbols and remaining bare commands/braces are then cleaned up.
    """
    prev = None
    while prev != text:
        prev = text
        text = _STRIP_COMMAND_RE.sub(r"\1", text)
    text = text.replace(r"\%", "%").replace(r"\$", "$").replace(r"\&", "&")
    text = text.replace(r"\hfill", " ").replace("\\\\", " ")
    text = _BARE_COMMAND_RE.sub("", text)
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_command_arg(text: str, brace_index: int) -> tuple[str, int]:
    """Given ``text[brace_index] == '{'``, return (content, index just past the matching '}')."""
    depth = 0
    for i in range(brace_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_index + 1 : i], i + 1
    raise ValueError("Unbalanced braces in LaTeX source")


def find_command_args(text: str, command: str) -> list[str]:
    """Every top-level (non-nested) argument of ``\\command{...}`` in text.

    Balanced-brace aware: a nested ``\\textbf{--}`` inside a ``\\textit{...}``
    argument does not get returned as a separate, spurious match, and does
    not break finding the outer argument's true closing brace.
    """
    pattern = re.compile(rf"\\{re.escape(command)}\s*")
    results: list[str] = []
    pos = 0
    while True:
        match = pattern.search(text, pos)
        if match is None:
            break
        brace_index = match.end()
        if brace_index >= len(text) or text[brace_index] != "{":
            pos = match.end()
            continue
        content, end_index = _extract_command_arg(text, brace_index)
        results.append(content)
        pos = end_index
    return results


def parse_sections(latex: str) -> dict[str, str]:
    """Split the document body into ``{section_name: raw_section_latex}``."""
    body_match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", latex, re.S)
    body = body_match.group(1) if body_match else latex

    parts = re.split(r"\\section\*?\s*\{([^{}]*)\}", body)
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        name = strip_latex_markup(parts[i])
        content = parts[i + 1] if i + 1 < len(parts) else ""
        sections[name] = content
    return sections


def parse_entries(section_latex: str) -> list[DraftEntry]:
    """Split one section's LaTeX into organization/project entries with their bullets.

    An entry is the text immediately preceding one ``itemize`` block (its
    "header": organization/project name, role or skill list, and date
    range) plus that block's ``\\item`` bullets.
    """
    entries: list[DraftEntry] = []
    pos = 0
    for match in re.finditer(r"\\begin\{itemize\}(.*?)\\end\{itemize\}", section_latex, re.S):
        header_text = section_latex[pos : match.start()]
        itemize_body = match.group(1)
        pos = match.end()

        textbf_args = find_command_args(header_text, "textbf")
        textit_args = find_command_args(header_text, "textit")
        organization = strip_latex_markup(textbf_args[0]) if textbf_args else "Unknown"
        role_or_skills = strip_latex_markup(textit_args[0]) if textit_args else ""

        hfill_positions = [m.end() for m in re.finditer(r"\\hfill", header_text)]
        date_range = strip_latex_markup(header_text[hfill_positions[-1] :]) if hfill_positions else ""

        raw_items = re.findall(r"\\item\s+(.*?)(?=\\item|\Z)", itemize_body, re.S)
        bullets = [strip_latex_markup(item) for item in raw_items]
        bullets = [b for b in bullets if b]

        entries.append(
            DraftEntry(
                organization=organization,
                role_or_skills=role_or_skills,
                date_range=date_range,
                raw_header=header_text,
                bullets=bullets,
            )
        )
    return entries


def parse_resume(latex: str) -> dict[str, list[DraftEntry]]:
    """Every section's entries, keyed by section name (e.g. "Experience", "Projects")."""
    return {name: parse_entries(content) for name, content in parse_sections(latex).items()}
