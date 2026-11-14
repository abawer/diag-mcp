"""Shared fixtures for diag-mcp unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server import config
from mcp_server.logs import _load_all
from mcp_server.models import LogLine

DEMO_DATA = Path(__file__).resolve().parent.parent / "demo_data"


@pytest.fixture
def log_lines() -> list[LogLine]:
    """The canonical demo transcript as LogLine objects."""
    return _load_all()


@pytest.fixture
def tmp_logs(tmp_path: Path, log_lines: list[LogLine], monkeypatch) -> Path:
    """A jsonl fixture with the canonical transcript; re-points config.LOGS_PATH at it."""
    path = tmp_path / "logs.jsonl"
    path.write_text("".join(json.dumps(e.model_dump()) + "\n" for e in log_lines),
                    encoding="utf-8")
    monkeypatch.setattr(config, "LOGS_PATH", str(path))
    return path


@pytest.fixture
def tmp_topology(tmp_path: Path, monkeypatch) -> Path:
    """A topology fixture; re-points config.TOPOLOGY_PATH at it."""
    path = tmp_path / "topology.json"
    path.write_text((DEMO_DATA / "topology.json").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(config, "TOPOLOGY_PATH", str(path))
    return path
