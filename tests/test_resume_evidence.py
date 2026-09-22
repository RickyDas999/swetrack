"""Evidence library loading and validation (synthetic fixtures + the real checked-in evidence.yaml)."""

from __future__ import annotations

from pathlib import Path

import pytest

from swetrack.domains.resume.evidence import DEFAULT_EVIDENCE_PATH, EvidenceLibraryError, load_evidence_library


def test_default_evidence_library_loads_and_validates() -> None:
    items = load_evidence_library(DEFAULT_EVIDENCE_PATH)
    assert len(items) > 0
    assert all(item.base_text for item in items)


def test_disabled_evidence_items_carry_a_review_note() -> None:
    items = load_evidence_library(DEFAULT_EVIDENCE_PATH)
    disabled = [item for item in items if not item.enabled]
    assert disabled  # the SWETrack PostgreSQL/React discrepancy items
    assert all(item.review_note for item in disabled)


def test_missing_file_raises_evidence_library_error(tmp_path: Path) -> None:
    with pytest.raises(EvidenceLibraryError):
        load_evidence_library(tmp_path / "does_not_exist.yaml")


def test_duplicate_ids_raise(tmp_path: Path) -> None:
    path = tmp_path / "evidence.yaml"
    path.write_text(
        "evidence:\n"
        "  - id: dup-1\n    section: experience\n    organization: X\n    base_text: A\n"
        "  - id: dup-1\n    section: experience\n    organization: Y\n    base_text: B\n"
    )
    with pytest.raises(EvidenceLibraryError):
        load_evidence_library(path)


def test_missing_top_level_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "evidence.yaml"
    path.write_text("not_evidence: []\n")
    with pytest.raises(EvidenceLibraryError):
        load_evidence_library(path)
