"""Config module tests."""

from __future__ import annotations

from mcp_server.config import LLM_TIMEOUT_S, DIAG_MCP_MODEL, TOPOLOGY_PATH


def test_defaults_are_sane() -> None:
    assert DIAG_MCP_MODEL  # non-empty default model
    assert LLM_TIMEOUT_S > 0
    assert TOPOLOGY_PATH  # points somewhere concrete


def test_paths_are_absolute() -> None:
    assert TOPOLOGY_PATH.startswith("/")
