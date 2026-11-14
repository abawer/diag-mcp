"""Pydantic schema tests — the RCA report contract (blueprint Section 2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_server.models import Evidence, RCAReport


def _report(**overrides) -> RCAReport:
    base = {
        "root_cause": "ENOSPC on telemetry-writer tmpfs",
        "evidence": [],
        "timeline": [],
        "fix": {"dry_run_command": "kubectl ...", "diff_summary": "..."},
        "confidence": 0.9,
    }
    base.update(overrides)
    return RCAReport.model_validate(base)


def test_valid_report_roundtrip() -> None:
    r = _report(evidence=[Evidence(service="s", timestamp="2026-11-14T10:00:00.000Z",
                                    raw_line="x", role="root_cause")])
    assert r.insufficient_evidence is False
    assert r.unrelated_findings == []
    assert r.fix.requires_hitl_approval is True


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_bounds_rejected(confidence: float) -> None:
    with pytest.raises(ValidationError):
        _report(confidence=confidence)


@pytest.mark.parametrize("role", ["root_cause", "propagation", "symptom", "excluded", "unrelated"])
def test_evidence_roles_accepted(role: str) -> None:
    e = Evidence(service="s", timestamp="t", raw_line="l", role=role)  # type: ignore[arg-type]
    assert e.role == role


@pytest.mark.parametrize("role", ["cause", "noise", "ROOT_CAUSE", ""])
def test_evidence_roles_rejected(role: str) -> None:
    with pytest.raises(ValidationError):
        Evidence(service="s", timestamp="t", raw_line="l", role=role)  # type: ignore[arg-type]


def test_missing_citation_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Evidence(service="s").model_validate({"service": "s"})
