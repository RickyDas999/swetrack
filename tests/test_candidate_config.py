"""Candidate eligibility profile loading (Job Radar Checkpoint 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from swetrack.domains.jobs.candidate_config import (
    DEFAULT_CANDIDATE_CONFIG_PATH,
    CandidateConfigError,
    load_candidate_eligibility_profile,
)


def test_default_example_candidate_config_loads_and_validates() -> None:
    profile = load_candidate_eligibility_profile(DEFAULT_CANDIDATE_CONFIG_PATH)
    assert profile.graduation_year == 2026
    assert profile.work_authorization.sponsorship_required is False
    assert "Senior" in profile.excluded_levels


def test_missing_file_raises_candidate_config_error(tmp_path: Path) -> None:
    with pytest.raises(CandidateConfigError):
        load_candidate_eligibility_profile(tmp_path / "does_not_exist.yaml")


def test_invalid_config_raises_candidate_config_error(tmp_path: Path) -> None:
    path = tmp_path / "candidate.yaml"
    path.write_text("graduation_year: not-a-year\n")
    with pytest.raises(CandidateConfigError):
        load_candidate_eligibility_profile(path)


def test_missing_name_raises_candidate_config_error(tmp_path: Path) -> None:
    path = tmp_path / "candidate.yaml"
    path.write_text("graduation_year: 2026\n")
    with pytest.raises(CandidateConfigError):
        load_candidate_eligibility_profile(path)
