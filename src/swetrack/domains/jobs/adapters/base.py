"""Shared adapter interface, HTTP helper, and text-sanitization helper for every job source."""

from __future__ import annotations

import html as html_lib
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Protocol

import httpx

from swetrack.domains.jobs.schemas import NormalizedJob

USER_AGENT = "SWETrack-JobRadar/0.1 (personal, non-commercial job search tool)"
DEFAULT_TIMEOUT_SECONDS = 10.0


class SourceAdapter(Protocol):
    """One job source (an ATS board, a manual import, ...).

    ``fetch()`` returns every currently-listed job as a ``NormalizedJob``,
    doing no deduplication, persistence, or scoring -- that is
    ``domains/jobs/services.py``, added in Checkpoint 2.
    """

    source_type: str

    def fetch(self) -> list[NormalizedJob]: ...


def http_get_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """GET ``url`` and return its parsed JSON body.

    Reuses ``client`` when given one (e.g. one wired to an
    ``httpx.MockTransport`` in tests, per
    SWETrack_Job_Radar_Claude_Code_Handoff.md Section 17: "CI must not depend
    on live ATS availability"); otherwise opens and closes a short-lived
    client for this one request.
    """
    owned_client = client or httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
    try:
        response = owned_client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    finally:
        if client is None:
            owned_client.close()


def parse_iso_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp from an ATS payload, or None for missing/malformed input.

    Never raises: this is untrusted external data, and one unexpected date
    format on one job must not fail an entire sync.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._chunks).split())


def strip_html_to_text(raw_html: str) -> str:
    """Plain text from an ATS description field.

    Job descriptions are untrusted external content
    (SWETrack_Job_Radar_Claude_Code_Handoff.md Section 16: "sanitize HTML to
    plain text. Never render source HTML unsafely."). This only ever
    extracts text nodes -- it never executes, evaluates, or re-renders markup.

    Some ATS platforms (confirmed: Greenhouse's `content` field) return
    this text already HTML-entity-escaped once on top of the real markup
    (e.g. the literal characters ``&lt;div&gt;`` instead of ``<div>``).
    Unescaping is repeated to a fixed point first so the real tags are
    visible to the parser below -- otherwise they're left as literal
    "&lt;"/"&gt;" text that never gets recognized as a tag, and the "plain
    text" this function returns still contains a full HTML document.
    """
    if not raw_html:
        return ""
    text = raw_html
    previous = None
    while previous != text:
        previous = text
        text = html_lib.unescape(text)
    parser = _TextExtractor()
    parser.feed(text)
    return parser.text()
