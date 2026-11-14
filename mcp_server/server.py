"""diag-mcp Web MCP server (FastMCP, streamable-http, port 8000).

Tools (read-only):
  1. get_service_topology(service, hops=2) -> TopologyGraph
  2. fetch_service_logs(service, since?, until?, severity, regex_filter, limit) -> list[LogLine]
  3. check_os_resources(service) -> OSReport
  4. analyze_crash_llm(log_excerpt, topology, os_report) -> RCAReport  (live Anthropic API)
"""

from __future__ import annotations

from fastmcp import FastMCP

from .llm import analyze_crash
from .logs import fetch_service_logs as _fetch_service_logs
from .models import OSReport, RCAReport, TopologyGraph
from .oshealth import check_os_resources as _check_os_resources
from .topology import get_service_topology as _get_service_topology

mcp = FastMCP(name="diag-mcp", version="0.1.0")


@mcp.tool()
def get_service_topology(service: str, hops: int = 2) -> TopologyGraph:
    """Return the architectural dependency subgraph around a service (POC: topology.json; prod: Neo4j)."""
    return _get_service_topology(service=service, hops=hops)


@mcp.tool()
def fetch_service_logs(
    service: str,
    since: str | None = None,
    until: str | None = None,
    severity: str = "WARN",
    regex_filter: str | None = None,
    limit: int = 200,
) -> list:
    """Deterministically filtered logs: time window -> severity gate -> regex -> dedup -> cap.

    `since`/`until` are optional UTC ISO-8601 bounds; omit them to scan the
    whole transcript and surface the most recent ERR/WARN lines.
    """
    return [entry.model_dump() for entry in
            _fetch_service_logs(service=service, since=since, until=until,
                                severity=severity, regex_filter=regex_filter, limit=limit)]


@mcp.tool()
def check_os_resources(service: str) -> OSReport:
    """Structured df -h, memory, and kernel alerts (dmesg ENOSPC/OOM) for a service. Read-only."""
    return _check_os_resources(service=service)


@mcp.tool()
def analyze_crash_llm(log_excerpt: str, topology: dict, os_report: dict) -> RCAReport:
    """Live Anthropic API call classifying root cause; requires timestamped verbatim citations."""
    from .models import AnalyzeCrashInput

    inp = AnalyzeCrashInput(log_excerpt=log_excerpt,
                            topology=TopologyGraph.model_validate(topology),
                            os_report=OSReport.model_validate(os_report))
    return analyze_crash(inp)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
