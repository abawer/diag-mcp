"""Unit tests for analyze_crash_llm — fail-closed behavior and request shape.

The live API call is never exercised here (no key, no network); the HTTP layer is
stubbed via httpx's transport mock so we can still assert on the request payload
and the response-parsing path.
"""

from __future__ import annotations

import json as json_mod

import httpx
import pytest

from mcp_server import config
from mcp_server.llm import analyze_crash_llm
from mcp_server.models import OSReport, TopologyGraph


def _topo() -> TopologyGraph:
    return TopologyGraph(root="api-gateway", nodes=[], edges=[])


def _os() -> OSReport:
    return OSReport(service="telemetry-writer", disk={}, memory={}, kernel_alerts=["ENOSPC"])


def _valid_report() -> dict:
    return {
        "root_cause": "ENOSPC on telemetry-writer tmpfs",
        "evidence": [{"service": "telemetry-writer",
                      "timestamp": "2026-11-14T10:00:00.000Z",
                      "raw_line": "[disk] ENOSPC: No space left on device",
                      "role": "root_cause"}],
        "timeline": [{"t_offset_ms": 0, "service": "telemetry-writer", "event": "ENOSPC"}],
        "fix": {"dry_run_command": "kubectl ...", "diff_summary": "..."},
        "confidence": 0.9,
        "unrelated_findings": [],
    }


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def test_missing_api_key_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        analyze_crash_llm("x", {}, {})


def test_happy_path_returns_report(monkeypatch) -> None:
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    captured = {}

    def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["payload"] = json
        captured["headers"] = headers
        return _Response({"content": [{"type": "text", "text": json_mod.dumps(_valid_report())}]})

    monkeypatch.setattr("mcp_server.llm.httpx.Client.post", fake_post)
    report = analyze_crash_llm("excerpt", _topo().model_dump(), _os().model_dump())

    assert report.root_cause == "ENOSPC on telemetry-writer tmpfs"
    assert captured["url"].endswith("/v1/messages")
    assert captured["payload"]["model"] == config.DIAG_MCP_MODEL
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


def test_api_error_is_not_swallowed(monkeypatch) -> None:
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    def boom(self, url, json=None, headers=None):
        raise httpx.HTTPStatusError("500", request=None, response=None)  # type: ignore[arg-type]

    monkeypatch.setattr("mcp_server.llm.httpx.Client.post", boom)
    with pytest.raises(httpx.HTTPStatusError):
        analyze_crash_llm("excerpt", {}, {})


def test_invalid_schema_from_llm_is_rejected(monkeypatch) -> None:
    """LLM returns JSON that doesn't match RCAReport -> pydantic rejects, never a silent guess."""
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    def fake_post(url, json_payload, headers):
        return _Response({"content": [{"type": "text", "text": json.dumps({"root_cause": "x"})}]})

    monkeypatch.setattr("mcp_server.llm.httpx.Client.post", fake_post)
    with pytest.raises(Exception):  # ValidationError from pydantic
        analyze_crash_llm("excerpt", {}, {})


def test_citation_requirement_is_in_system_prompt() -> None:
    """The system prompt must force verbatim citations (blueprint Section 4D)."""
    import mcp_server.llm as llm_mod
    assert "verbatim" in llm_mod.SYSTEM_PROMPT
    assert "insufficient_evidence" in llm_mod.SYSTEM_PROMPT
