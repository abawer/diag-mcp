"""Server configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
# DIAG_MCP_MODEL is canonical; MCP_DIAG_MODEL is accepted as an alias (the
# blueprint spells it MCP_DIAG_MODEL). DIAG_MCP_MODEL wins if both are set.
DIAG_MCP_MODEL: str = (
    os.environ.get("DIAG_MCP_MODEL")
    or os.environ.get("MCP_DIAG_MODEL")
    or "claude-sonnet-5-5"
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEMO = _REPO_ROOT / "demo_data"
TOPOLOGY_PATH: str = os.environ.get("TOPOLOGY_PATH", str(_DEMO / "topology.yaml"))
LOGS_PATH: str = os.environ.get("LOGS_PATH", str(_DEMO / "logs.jsonl"))
OS_PATH: str = os.environ.get("OS_PATH", str(_DEMO / "os.json"))
LLM_TIMEOUT_S: float = float(os.environ.get("DIAG_MCP_LLM_TIMEOUT_S", "60"))
