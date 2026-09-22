"""Loading and validation of the evidence library (resume/evidence.yaml).

Mirrors opportunities/config.py's load_jobs pattern: YAML in, validated
Pydantic models out, a clear domain-specific error on any problem.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from swetrack.domains.resume.schemas import EvidenceItem
from swetrack.infrastructure.paths import find_repo_root

DEFAULT_EVIDENCE_PATH = find_repo_root() / "resume" / "evidence.yaml"


class EvidenceLibraryError(ValueError):
    """Raised when the evidence library YAML fails to load or validate."""


def load_evidence_library(path: str | Path = DEFAULT_EVIDENCE_PATH) -> list[EvidenceItem]:
    """Load and validate every evidence item from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise EvidenceLibraryError(f"Evidence library file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    entries_raw = raw.get("evidence")
    if entries_raw is None:
        raise EvidenceLibraryError(f"Evidence library {path} must have a top-level 'evidence' list")

    items: list[EvidenceItem] = []
    seen_ids: set[str] = set()
    for index, entry_raw in enumerate(entries_raw, start=1):
        try:
            item = EvidenceItem.model_validate(entry_raw)
        except ValidationError as exc:
            raise EvidenceLibraryError(f"Invalid evidence item #{index} in {path}: {exc}") from exc
        if item.id in seen_ids:
            raise EvidenceLibraryError(f"Duplicate evidence id {item.id!r} in {path}")
        seen_ids.add(item.id)
        items.append(item)

    return items


def get_evidence_by_id(items: list[EvidenceItem], evidence_id: str) -> EvidenceItem | None:
    return next((item for item in items if item.id == evidence_id), None)
