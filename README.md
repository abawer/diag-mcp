# diag-mcp

Topology-aware root-cause analysis (RCA) diagnostics agent: Claude Code + a centralized
Web MCP server. See [mcp-diag-blueprint.md](mcp-diag-blueprint.md) for the full design.

## Day-1 components
- `mcp_server/` — FastMCP server (streamable-http, port 8000), 4 read-only tools.
- `topology.json` / `demo_data/` — POC topology + canonical log/OS fixtures.
- `Dockerfile` / `docker-compose.yml` — containerized server.
- `CLAUDE.md` — guardrails: read-only, citations, HITL, unrelated-findings rule.

## Run (no Docker daemon needed)
```bash
cp .env.example .env   # add ANTHROPIC_API_KEY for analyze_crash_llm
./scripts/dev.sh       # serves on http://localhost:8000/mcp
```

## Tests
```bash
python3 -m pytest tests/ -q      # 45 unit tests, no API key or network required
```
Covers: Pydantic schema bounds, topology hops, log filtering/dedup, OS report,
LLM fail-closed + request shape, and the MCP tool registry/handlers.

## Tools
| Tool | Purpose |
|---|---|
| `get_service_topology` | Dependency subgraph (POC: YAML; prod: Neo4j) |
| `fetch_service_logs` | Deterministic pre-LLM log filtering |
| `check_os_resources` | df/memory/kernel alerts, read-only |
| `analyze_crash_llm` | Live Anthropic API, Pydantic RCA report |
