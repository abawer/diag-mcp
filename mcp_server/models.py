"""Pydantic models for the diag-mcp MCP server.

Contracts match mcp-diag-blueprint.md Section 2/3 exactly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TopologyNode(BaseModel):
    name: str
    kind: str
    notes: str = ""
    downstream: list[str] = Field(default_factory=list)


class TopologyGraph(BaseModel):
    root: str
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[tuple[str, str]] = Field(default_factory=list)


class LogLine(BaseModel):
    timestamp: str  # UTC ISO-8601, millisecond precision
    service: str
    level: str
    line: str  # verbatim log content


class OSReport(BaseModel):
    service: str
    disk: dict
    memory: dict
    kernel_alerts: list[str]


class Evidence(BaseModel):
    service: str
    timestamp: str  # UTC ISO-8601, e.g. 2026-11-14T10:00:00.005Z; must match a transcript line exactly
    raw_line: str  # verbatim citation
    role: Literal["root_cause", "propagation", "symptom", "excluded", "unrelated"]


class TimelineStep(BaseModel):
    timestamp: str  # UTC ISO-8601, verbatim from the log line; never derived
    service: str
    event: str


class FixProposal(BaseModel):
    dry_run_command: str
    diff_summary: str
    requires_hitl_approval: bool = True


class RCAReport(BaseModel):
    root_cause: str
    evidence: list[Evidence]
    timeline: list[TimelineStep]
    fix: FixProposal
    confidence: float = Field(ge=0.0, le=1.0)
    insufficient_evidence: bool = False  # must be True when citations are missing
    unrelated_findings: list[Evidence] = Field(default_factory=list)  # real, cited issues outside the cascade


class AnalyzeCrashInput(BaseModel):
    log_excerpt: str
    topology: TopologyGraph
    os_report: OSReport
