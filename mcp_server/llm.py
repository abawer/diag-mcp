"""analyze_crash_llm: live Anthropic Messages API call with Pydantic-structured output.

Fail-closed: any error surfaces as a clear exception, never a guessed diagnosis.
Schema requires timestamped verbatim citations; missing citations =>
insufficient_evidence=True.
"""

from __future__ import annotations

import json

import httpx

from . import config
from .models import AnalyzeCrashInput, RCAReport

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """\
You are a root-cause analysis engine. Given a log excerpt, a service topology graph,
and an OS resource report, produce a diagnosis.

Hard rules:
1. Every claim MUST cite a verbatim log line with its exact UTC ISO-8601 timestamp.
2. If the citations are missing or incomplete, set insufficient_evidence=true and do
   NOT speculate.
3. Correlate timestamps across layers to order the cascade (root cause -> propagation
   -> symptom).
4. Issues that are real but do NOT correlate with the cascade go in unrelated_findings,
   never folded into root_cause.
5. The fix must be a dry-run command/diff only; state requires_hitl_approval=true.

Output ONLY the JSON matching the RCAReport schema."""


def analyze_crash_llm(log_excerpt: str, topology: dict, os_report: dict) -> RCAReport:
    """Call the Anthropic Messages API and validate the structured result."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; cannot call analyze_crash_llm")

    payload = {
        "model": config.DIAG_MCP_MODEL,
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": json.dumps({
                    "log_excerpt": log_excerpt,
                    "topology": topology,
                    "os_report": os_report,
                }),
            }
        ],
    }

    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
        resp = client.post(API_URL, json=payload, headers=headers)
    resp.raise_for_status()

    body = resp.json()
    text = "".join(block.get("text", "") for block in body.get("content", [])
                   if block.get("type") == "text")
    report = RCAReport.model_validate(json.loads(text))
    return report


def analyze_crash(inp: AnalyzeCrashInput) -> RCAReport:
    """MCP-facing wrapper: typed input -> dict -> API -> typed report."""
    return analyze_crash_llm(
        log_excerpt=inp.log_excerpt,
        topology=inp.topology.model_dump(),
        os_report=inp.os_report.model_dump(),
    )
