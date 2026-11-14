"""MCP server tool tests — call the registered @mcp.tool() handlers directly.

This is the standard way to test tools without a live HTTP session or Docker:
the same call path Claude Code uses, minus the transport. Results arrive as
TextContent with a JSON string in .text.
"""

from __future__ import annotations

import json

import pytest

from mcp_server.server import mcp


async def _call(name: str, args: dict) -> dict:
    r = await mcp.call_tool(name, args)
    return json.loads(r.content[0].text)


@pytest.mark.asyncio
async def test_tool_registry_matches_blueprint() -> None:
    tools = {t.name for t in await mcp.list_tools()}
    assert tools == {"get_service_topology", "fetch_service_logs",
                     "check_os_resources", "analyze_crash_llm"}


@pytest.mark.asyncio
async def test_get_service_topology_tool(tmp_topology) -> None:
    data = await _call("get_service_topology", {"service": "api-gateway", "hops": 2})
    names = {n["name"] for n in data["nodes"]}
    assert "telemetry-writer" in names and "nvme-tmpfs" in names
    assert data["root"] == "api-gateway"


@pytest.mark.asyncio
async def test_fetch_service_logs_tool(tmp_logs) -> None:
    data = await _call("fetch_service_logs", {
        "service": "telemetry-writer",
        "since": "2026-11-14T10:00:00.000Z",
        "until": "2026-11-14T10:00:01.000Z",
    })
    lines = [item["line"] for item in data]
    assert any("ENOSPC" in l for l in lines)
    assert any("503" in l for l in lines)


@pytest.mark.asyncio
async def test_check_os_resources_tool() -> None:
    data = await _call("check_os_resources", {"service": "telemetry-writer"})
    assert data["disk"]["used"] == "100%"
    assert any("ENOSPC" in a for a in data["kernel_alerts"])


@pytest.mark.asyncio
async def test_analyze_crash_llm_tool_fails_closed_without_key(monkeypatch) -> None:
    from mcp_server import config
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    # call_tool wraps tool exceptions, so match on the message, not the type.
    with pytest.raises(Exception, match="ANTHROPIC_API_KEY"):
        await mcp.call_tool("analyze_crash_llm", {
            "log_excerpt": "x", "topology": {"root": "a", "nodes": [], "edges": []},
            "os_report": {"service": "s", "disk": {}, "memory": {}, "kernel_alerts": []},
        })
