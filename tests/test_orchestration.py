"""Shared per-source sync orchestration: failure isolation and health tracking (Checkpoint 8)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from swetrack.domains.jobs import orchestration as orchestration_module
from swetrack.domains.jobs.orchestration import sync_registry_sources
from swetrack.domains.jobs.schemas import NormalizedJob, SourceRegistryEntry
from swetrack.domains.jobs.source_health import list_source_health


class _FakeAdapter:
    def __init__(self, jobs=None, error: Exception | None = None):
        self._jobs = jobs or []
        self._error = error

    def fetch(self):
        if self._error:
            raise self._error
        return self._jobs


def _entry(company: str, token: str, *, enabled: bool = True) -> SourceRegistryEntry:
    return SourceRegistryEntry(company=company, adapter="greenhouse", token=token, enabled=enabled)


def test_a_failing_source_does_not_abort_the_whole_run(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    good_job = NormalizedJob(
        source_type="greenhouse",
        source_job_id="1",
        company_name="Good Co",
        title="Software Engineer, New Grad",
        application_url="https://example.com/1",
        source_url="https://example.com/1",
    )
    adapters_by_token = {"good": _FakeAdapter(jobs=[good_job]), "bad": _FakeAdapter(error=RuntimeError("simulated 404"))}
    monkeypatch.setattr(orchestration_module, "build_adapter", lambda entry: adapters_by_token[entry.token])

    entries = [_entry("Good Co", "good"), _entry("Bad Co", "bad")]
    outcomes = sync_registry_sources(db_session, entries)

    assert len(outcomes) == 2
    good_outcome = next(o for o in outcomes if o.entry.company == "Good Co")
    bad_outcome = next(o for o in outcomes if o.entry.company == "Bad Co")

    assert good_outcome.error is None
    assert good_outcome.result.new_count == 1
    assert bad_outcome.error == "simulated 404"
    assert bad_outcome.result is None


def test_disabled_sources_are_skipped(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestration_module, "build_adapter", lambda entry: _FakeAdapter())
    outcomes = sync_registry_sources(db_session, [_entry("Disabled Co", "x", enabled=False)])
    assert outcomes == []


def test_health_is_recorded_for_both_success_and_failure(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    adapters_by_token = {"good": _FakeAdapter(jobs=[]), "bad": _FakeAdapter(error=RuntimeError("boom"))}
    monkeypatch.setattr(orchestration_module, "build_adapter", lambda entry: adapters_by_token[entry.token])

    sync_registry_sources(db_session, [_entry("Good Co", "good"), _entry("Bad Co", "bad")])

    health = {h.source_key: h for h in list_source_health(db_session)}
    assert health["greenhouse:good"].total_success_count == 1
    assert health["greenhouse:bad"].total_failure_count == 1
    assert health["greenhouse:bad"].last_error == "boom"
