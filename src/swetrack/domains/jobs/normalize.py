"""Deterministic text/URL canonicalization for cross-source job matching.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 8. Intentionally simple:
lowercase + whitespace/punctuation folding, not full Unicode NFKD
normalization or a state-name/remote-label synonym dictionary. Add those if
a real duplicate is ever missed because of them -- CLAUDE.md: "Do not use
embeddings merely because they are available if deterministic normalization
is sufficient" applies just as well to over-building deterministic rules
nobody has needed yet.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]")

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_NAMES = {"gh_src", "gh_jid", "lever-source", "ref", "source", "trk"}


def _normalize_text(value: str) -> str:
    lowered = _PUNCTUATION_RE.sub(" ", value.lower())
    return _WHITESPACE_RE.sub(" ", lowered).strip()


def normalize_company_name(name: str) -> str:
    return _normalize_text(name)


def normalize_title(title: str) -> str:
    return _normalize_text(title)


def normalize_location(location: str) -> str:
    return _normalize_text(location)


def cross_source_key(company_name: str, title: str, location_text: str) -> str:
    """A best-effort identity for "probably the same job" across sources.

    Confirmed as a duplicate only when this also agrees on URL or
    description (services.py) -- Section 8, rule 5: "Confirm a fuzzy
    duplicate only when description similarity or official URL also agrees."
    """
    return "|".join((normalize_company_name(company_name), normalize_title(title), normalize_location(location_text)))


def strip_tracking_params(url: str) -> str:
    """Drop known tracking query parameters from a job URL, keeping the rest."""
    if not url:
        return url
    parsed = urlparse(url)
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAM_NAMES and not key.lower().startswith(_TRACKING_PARAM_PREFIXES)
    ]
    return urlunparse(parsed._replace(query=urlencode(kept)))
