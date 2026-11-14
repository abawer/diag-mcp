"""Unit tests for check_os_resources."""

from __future__ import annotations

import pytest

from mcp_server.oshealth import check_os_resources


def test_telemetry_writer_enospc_ground_truth() -> None:
    r = check_os_resources("telemetry-writer")
    assert r.service == "telemetry-writer"
    assert r.disk["used"] == "100%"
    assert any("ENOSPC" in a for a in r.kernel_alerts)


def test_healthy_service_has_no_alerts() -> None:
    r = check_os_resources("auth-service")
    assert r.kernel_alerts == []
    assert r.disk["used"] != "100%"


def test_unknown_service_raises() -> None:
    with pytest.raises(ValueError, match="unknown service"):
        check_os_resources("ghost")
