"""Source registry loading, validation, and adapter construction (Job Radar Checkpoint 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from swetrack.domains.jobs.adapters.ashby import AshbyAdapter
from swetrack.domains.jobs.adapters.greenhouse import GreenhouseAdapter
from swetrack.domains.jobs.adapters.lever import LeverAdapter
from swetrack.domains.jobs.registry import DEFAULT_SOURCES_PATH, SourceRegistryError, build_adapter, load_source_registry


def test_default_example_registry_loads_and_validates() -> None:
    entries = load_source_registry(DEFAULT_SOURCES_PATH)
    assert len(entries) == 3
    assert {entry.adapter for entry in entries} == {"greenhouse", "lever", "ashby"}
    assert all(entry.enabled for entry in entries)


def test_build_adapter_returns_the_matching_adapter_type() -> None:
    entries = load_source_registry(DEFAULT_SOURCES_PATH)
    by_adapter = {entry.adapter: entry for entry in entries}

    assert isinstance(build_adapter(by_adapter["greenhouse"]), GreenhouseAdapter)
    assert isinstance(build_adapter(by_adapter["lever"]), LeverAdapter)
    assert isinstance(build_adapter(by_adapter["ashby"]), AshbyAdapter)


def test_missing_file_raises_source_registry_error(tmp_path: Path) -> None:
    with pytest.raises(SourceRegistryError):
        load_source_registry(tmp_path / "does_not_exist.yaml")


def test_missing_identifier_for_adapter_raises(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - company: Example Co\n    adapter: greenhouse\n    enabled: true\n")
    with pytest.raises(SourceRegistryError):
        load_source_registry(path)


def test_duplicate_entries_raise(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - company: Example Co\n    adapter: greenhouse\n    token: exampleco\n"
        "  - company: Example Co Two\n    adapter: greenhouse\n    token: exampleco\n"
    )
    with pytest.raises(SourceRegistryError):
        load_source_registry(path)


def test_empty_sources_list_raises(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("sources: []\n")
    with pytest.raises(SourceRegistryError):
        load_source_registry(path)


def test_disabled_entry_still_loads_but_flagged(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - company: Example Co\n    adapter: greenhouse\n    token: exampleco\n    enabled: false\n")
    entries = load_source_registry(path)
    assert len(entries) == 1
    assert entries[0].enabled is False
