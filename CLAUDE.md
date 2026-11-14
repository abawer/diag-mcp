# diag-mcp

Topology-aware RCA diagnostics agent: Claude Code + a centralized Web MCP server.

## Safety guardrails (non-negotiable)
- **Read-only by default.** Diagnostic tools never mutate state. No writes, no
  `kubectl delete`, no restarts.
- **Every claim needs a citation.** A claim without a verbatim log line + UTC timestamp
  is speculation. If evidence is missing, report `insufficient_evidence: true` — never
  guess.
- **HITL before any fix.** Fixes ship as a dry-run command + diff summary only. Executing
  a fix requires explicit human approval; the approval step is not optional.
- **Report unrelated findings separately.** Real issues that do not correlate with the
  cascade go in `unrelated_findings` — cited, but never folded into the root cause.

## Architecture
- `mcp_server/` — FastMCP server (streamable-http, port 8000), Dockerized.
  Tools: `get_service_topology`, `fetch_service_logs`, `check_os_resources`,
  `analyze_crash_llm` (live Anthropic API; needs `ANTHROPIC_API_KEY`).
- `topology.yaml` — POC topology source of truth.
- `demo_data/` — canonical log transcript + topology fixture.
- `.claude/skills/diagnose/SKILL.md`, `.claude/agents/*.md` — Day 3 (not yet created).

## Coding standards
- Python 3.12, Pydantic v2, `ruff` clean, type hints everywhere.
- Tool contracts match `mcp-diag-blueprint.md` Section 3 exactly; changing one means
  updating the blueprint in the same PR.
- UTC ISO-8601 with millisecond precision for all timestamps.

## Dev
```bash
cp .env.example .env   # ANTHROPIC_API_KEY=...
docker compose up --build   # or: ./scripts/dev.sh
```
Verify: `claude mcp list`, then `curl -X POST localhost:8000/mcp ...` (see blueprint).
