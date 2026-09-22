"""Truth gate: reject any selection referencing unknown/disabled/unverified evidence."""

from __future__ import annotations

from swetrack.domains.resume.schemas import EvidenceItem, SelectedEvidence
from swetrack.domains.resume.truth_gate import validate_selection

_GOOD_ITEM = EvidenceItem(
    id="good-1", section="experience", organization="Fake Co", base_text="Did a thing.", verified=True, enabled=True
)
_DISABLED_ITEM = EvidenceItem(
    id="disabled-1", section="project", organization="X", base_text="Claims a thing.", verified=False, enabled=False
)
_UNVERIFIED_BUT_ENABLED = EvidenceItem(
    id="unverified-1", section="project", organization="Y", base_text="Needs review.", verified=False, enabled=True
)
_EVIDENCE = [_GOOD_ITEM, _DISABLED_ITEM, _UNVERIFIED_BUT_ENABLED]


def _selected(evidence_id: str) -> list[SelectedEvidence]:
    return [SelectedEvidence(evidence_id=evidence_id, relevance_score=1.0, matched_skills=[])]


def test_valid_selection_has_no_violations() -> None:
    assert validate_selection(_selected("good-1"), _EVIDENCE) == []


def test_unknown_evidence_id_is_a_violation() -> None:
    violations = validate_selection(_selected("does-not-exist"), _EVIDENCE)
    assert len(violations) == 1
    assert violations[0].evidence_id == "does-not-exist"


def test_disabled_evidence_is_a_violation() -> None:
    violations = validate_selection(_selected("disabled-1"), _EVIDENCE)
    reasons = [v.reason for v in violations]
    assert any("disabled" in r.lower() for r in reasons)
    assert any("not verified" in r.lower() for r in reasons)


def test_unverified_but_enabled_evidence_is_a_violation() -> None:
    violations = validate_selection(_selected("unverified-1"), _EVIDENCE)
    assert len(violations) == 1
    assert "not verified" in violations[0].reason.lower()
