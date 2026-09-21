"""Shared adapter interface and text-sanitization helper for every job source."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Protocol

from swetrack.domains.jobs.schemas import NormalizedJob


class SourceAdapter(Protocol):
    """One job source (an ATS board, a manual import, ...).

    ``fetch()`` returns every currently-listed job as a ``NormalizedJob``,
    doing no deduplication, persistence, or scoring -- that is
    ``domains/jobs/services.py``, added in Checkpoint 2.
    """

    source_type: str

    def fetch(self) -> list[NormalizedJob]: ...


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._chunks).split())


def strip_html_to_text(html: str) -> str:
    """Plain text from an ATS description field.

    Job descriptions are untrusted external content
    (SWETrack_Job_Radar_Claude_Code_Handoff.md Section 16: "sanitize HTML to
    plain text. Never render source HTML unsafely."). This only ever
    extracts text nodes -- it never executes, evaluates, or re-renders markup.
    """
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()
