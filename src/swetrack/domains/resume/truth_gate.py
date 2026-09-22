"""Truth gate: reject any tailored resume assembly not fully traceable to approved evidence.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 11's truth gate. Every
selected bullet is rendered from its evidence item's ``base_text``/
``date_range`` verbatim (tailoring.py never rewrites text, only reorders
and selects), so this gate's job is narrower than a generic content
validator: confirm every referenced evidence_id actually exists, is
``enabled``, and is ``verified`` -- CLAUDE.md: "Every generated claim must
include evidence_id" and reject when "an inserted skill lacks verified
evidence" or "a company, project, title, or date changes."
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from swetrack.domains.resume.schemas import EvidenceItem, SelectedEvidence


class TruthGateViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    reason: str


def validate_selection(selected: list[SelectedEvidence], evidence: list[EvidenceItem]) -> list[TruthGateViolation]:
    """Every violation found in one proposed resume assembly. Empty list means it passes."""
    by_id = {item.id: item for item in evidence}
    violations: list[TruthGateViolation] = []

    for entry in selected:
        item = by_id.get(entry.evidence_id)
        if item is None:
            violations.append(TruthGateViolation(evidence_id=entry.evidence_id, reason="Unknown evidence id"))
            continue
        if not item.enabled:
            violations.append(TruthGateViolation(evidence_id=entry.evidence_id, reason="Evidence item is disabled"))
        if not item.verified:
            violations.append(
                TruthGateViolation(evidence_id=entry.evidence_id, reason=f"Evidence item is not verified: {item.review_note}")
            )
    return violations
