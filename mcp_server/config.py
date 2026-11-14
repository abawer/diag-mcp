"""Server configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL : str = "openrouter/free"
DIAG_MCP_MODEL: str = (
    os.environ.get("MCP_DIAG_MODEL")
    or DEFAULT_MODEL
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEMO = _REPO_ROOT / "demo_data"
TOPOLOGY_PATH: str = os.environ.get("TOPOLOGY_PATH", str(_DEMO / "topology.json"))
LOGS_PATH: str = os.environ.get("LOGS_PATH", str(_DEMO / "logs.jsonl"))
OS_PATH: str = os.environ.get("OS_PATH", str(_DEMO / "os.json"))
LLM_TIMEOUT_S: float = float(os.environ.get("DIAG_MCP_LLM_TIMEOUT_S", "60"))
