"""Loading, validation, and adapter construction for the source registry.

Mirrors opportunities/config.py's load_jobs/load_candidate_profile pattern:
YAML in, validated Pydantic models out, a clear domain-specific error on any
problem. Kept separate from schemas.py (which stays free of file I/O) and
from the adapters package (SourceRegistryEntry -> concrete adapter
construction lives here so adapters never need to import the registry).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from swetrack.domains.jobs.adapters.ashby import AshbyAdapter
from swetrack.domains.jobs.adapters.base import SourceAdapter
from swetrack.domains.jobs.adapters.greenhouse import GreenhouseAdapter
from swetrack.domains.jobs.adapters.lever import LeverAdapter
from swetrack.domains.jobs.schemas import SourceRegistryEntry
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_SOURCES_PATH = find_repo_root() / "config" / "sources.example.yaml"


class SourceRegistryError(ValueError):
    """Raised when the source registry YAML fails to load or validate."""


def load_source_registry(path: str | Path = DEFAULT_SOURCES_PATH) -> list[SourceRegistryEntry]:
    """Load and validate every source registry entry from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise SourceRegistryError(f"Source registry file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    entries_raw = raw.get("sources")
    if entries_raw is None:
        raise SourceRegistryError(f"Source registry {path} must have a top-level 'sources' list")

    entries: list[SourceRegistryEntry] = []
    seen_identities: set[tuple[str, str]] = set()
    for index, entry_raw in enumerate(entries_raw, start=1):
        try:
            entry = SourceRegistryEntry.model_validate(entry_raw)
        except ValidationError as exc:
            raise SourceRegistryError(f"Invalid source registry entry #{index} in {path}: {exc}") from exc

        identity = (entry.adapter, entry.token or entry.site or entry.board_name or "")
        if identity in seen_identities:
            raise SourceRegistryError(f"Duplicate source registry entry #{index} in {path}: {identity}")
        seen_identities.add(identity)
        entries.append(entry)

    if not entries:
        raise SourceRegistryError(f"No source registry entries found in {path}")
    return entries


def build_adapter(entry: SourceRegistryEntry) -> SourceAdapter:
    """Construct the concrete adapter instance for one validated registry entry."""
    if entry.adapter == "greenhouse":
        assert entry.token is not None  # enforced by SourceRegistryEntry's own validator
        return GreenhouseAdapter(entry.token, entry.company)
    if entry.adapter == "lever":
        assert entry.site is not None
        return LeverAdapter(entry.site, entry.company, region=entry.region)
    assert entry.board_name is not None
    return AshbyAdapter(entry.board_name, entry.company)
