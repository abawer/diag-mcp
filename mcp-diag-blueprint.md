# Project Blueprint: `diag-mcp`
**Topology-Aware Root Cause Analysis (RCA) & Diagnostics Agent**

## 1. Project Overview & Goals
`diag-mcp` is an internal Developer Experience (DevEx) and infrastructure diagnostics system built around **Claude Code** and a centralized **Web MCP (Model Context Protocol)** server.

The project demonstrates how an autonomous AI coding agent can diagnose complex, multi-layered **Cascading Failures** across distributed microservices—not by guessing from raw logs, but by understanding system topology, tracing dependencies backward in time, and isolating noisy signals.

### Concepts Covered
* **Agentic Coding Workflows:** Built and orchestrated using **Claude Code**, `CLAUDE.md`, custom `SKILL.md` workflows, and specialized **Sub-agents** (`.claude/agents/`).
* **Model Context Protocol (MCP):** Centralized Web MCP server (`streamable-http` transport) packaged in **Docker**.
* **Topology-Aware Reasoning:** Exposing system architecture (`topology.json` in POC; Neo4j Graph DB in production) as a deterministic tool before log inspection.
* **LLM Integration & Prompt Engineering:** Structured outputs via **Pydantic**, XML context isolation, and evidence-grounded citations.
* **Production Readiness:** Read-only guardrails, human-in-the-loop approvals, trajectory tracing, and automated regression evaluations (Evals).

---

## 2. Realistic Engineering Scenario (The Demo)
To avoid trivial single-service examples, `diag-mcp` simulates a realistic **API Gateway** routing traffic to three downstream services, where a low-level resource failure cascades into a misleading network symptom:

```text
                       ┌──► [ auth-service ]      (Healthy)
                       │
[ Client ] ──► [ API Gateway ] ──► [ routing-engine ]    (Impacted by GW congestion)
                       │
                       └──► [ telemetry-writer ] ──► [ NVMe / tmpfs 1MB ] (Root Cause!)
```

### The Cascading Failure Chain:
1. **Root Cause (Storage Layer):** `telemetry-writer` writes metrics to a Docker `tmpfs` mount capped at `1MB`. Under load, it hits `ENOSPC` (`No space left on device`) and starts returning slow `HTTP 503` errors.
2. **Propagation (Gateway Layer):** `api-gateway` shares a fixed worker thread pool across routes and retries failed requests to `telemetry-writer`. Threads saturate, blocking unrelated traffic.
3. **Misleading Symptom (Client & Network Layer):** `client-simulator` experiences timeouts even on healthy endpoints (`/routes` -> `routing-engine`) and triggers an aggressive retry storm, causing a massive spike in network traffic.

### Canonical Log Transcript (deterministic ground truth)
The fault injector emits exactly these lines (plus noise). Every RCA claim must cite one of them verbatim.
**All services log UTC ISO-8601 with millisecond precision** (e.g. `2026-11-14T10:00:00.005Z`) on NTP-synced hosts, so cross-service correlation is straight timestamp subtraction — no per-service clock translation. The `Δ` column is a *derived* annotation of the propagation delay, not what the logs contain.

| timestamp (UTC) | Δ | service | level | line |
|---|---|---|---|---|
| `2026-11-14T10:00:00.000Z` | t=0 | telemetry-writer | ERROR | `[disk] ENOSPC: No space left on device writing /metrics/2026-11-14.bin (tmpfs 1MB cap)` |
| `2026-11-14T10:00:00.005Z` | t+5ms | telemetry-writer | WARN | `[http] POST /metrics/ingest -> 503 (upstream write failed, latency=214ms)` |
| `2026-11-14T10:00:00.030Z` | t+30ms | routing-engine | INFO | `[jvm] GC pause 42ms (young gen) — within SLO` *(decoy: benign)* |
| `2026-11-14T10:00:00.040Z` | t+40ms | api-gateway | WARN | `[pool] worker pool exhausted: 64/64 threads blocked on telemetry-writer retry, queue=1024` |
| `2026-11-14T10:00:00.045Z` | t+45ms | routing-engine | WARN | `[net] TCP retransmits 2.1% on eth0` *(decoy: symptom, not cause)* |
| `2026-11-14T10:00:00.100Z` | t+100ms | client-simulator | ERROR | `[retry] POST /routes timed out after 2000ms (attempt 3/5), storm=480 req/s` |
| `2026-11-14T10:00:00.000Z` | t=0 | auth-service | INFO | `[deploy] rolling deploy v2.4.1 complete (canary=100%)` *(decoy: unrelated)* |

OS ground truth (`check_os_resources("telemetry-writer")`): tmpfs mount `1.0M 100% used`; `dmesg` shows `ENOSPC` on the metrics path (kernel timestamps also UTC). `auth-service` and `routing-engine` show healthy disk/memory.

### Expected Agent Resolution:
1. Queries `get_service_topology("api-gateway")` first to map all downstream dependencies.
2. Dispatches sub-agents to inspect logs and OS health across all branches in parallel.
3. Isolates `auth-service` and `routing-engine` as healthy at the OS/process level.
4. Correlates UTC timestamps across layers (subtracting them yields the propagation deltas): `Disk ENOSPC` (t=0) ➔ `telemetry-writer 503` (+5ms) ➔ `Gateway Thread Pool Exhaustion` (+40ms) ➔ `Client Retry Storm` (+100ms).
5. Outputs a structured RCA report with exact log citations, proposes a fix (requiring human approval), and lists **unrelated findings** separately — e.g. the `auth-service` deploy line is cited as `unrelated`: real, but not part of this cascade; never folded in, never dropped.

### Expected RCA Report Schema (Pydantic)
```python
class Evidence(BaseModel):
    service: str
    timestamp: str          # UTC ISO-8601, e.g. 2026-11-14T10:00:00.005Z; must match a transcript line exactly
    raw_line: str           # verbatim citation
    role: Literal["root_cause", "propagation", "symptom", "excluded", "unrelated"]

class TimelineStep(BaseModel):
    timestamp: str          # UTC ISO-8601, verbatim from the log line; never derived
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
    insufficient_evidence: bool = False   # must be True when citations are missing
    unrelated_findings: list[Evidence] = []  # real, cited issues outside the cascade
```

`excluded` = noise ruled out as a cause; `unrelated` = a genuine issue that simply doesn't correlate with this incident (e.g. the `auth-service` deploy line). Both require citations — never silence, never folding into the chain.

---

## 3. System Architecture & Components

```text
[ Developer Terminal: Claude Code ]
   ├── CLAUDE.md (Project rules, coding standards, safety guardrails)
   ├── .claude/skills/diagnose/SKILL.md (Deterministic RCA workflow)
   └── .claude/agents/
        ├── log-filter.md     (Context compression & semantic anomaly extraction)
        └── config-auditor.md (Read-only YAML/network config verification)
          │
          ▼ (Streamable HTTP over port 8000)
[ Docker Container: Web MCP Server (Python / FastMCP) ]
   ├── Tool 1: get_service_topology() -> Returns architectural dependency graph
   ├── Tool 2: fetch_service_logs()   -> Pre-filters noisy logs (Regex/time window)
   ├── Tool 3: check_os_resources()   -> Inspects disk (df -h), memory, and kernel alerts
   └── Tool 4: analyze_crash_llm()    -> Structured root-cause classification (Pydantic)
```

### Tool Contracts

| Tool | Signature | Behavior |
|---|---|---|
| `get_service_topology` | `(service: str, hops: int = 2) -> TopologyGraph` | Returns nodes, edges, per-node health. POC reads `topology.json`; production queries a Neo4j 2–3 hop subgraph around the alerting component. Node `notes` describe static architecture only (thread pools, mount caps, call patterns) — never the incident; the RCA must derive root cause and node health from cited evidence, not from topology metadata. |
| `fetch_service_logs` | `(service: str, since: str \| None = None, until: str \| None = None, severity: str = "WARN", regex_filter: str \| None = None, limit: int = 200) -> list[LogLine]` | Deterministic pre-LLM filtering: time-window slice ➜ severity gate ➜ regex match ➜ dedup by message-template fingerprint ➜ hard line cap. `since`/`until` are optional UTC ISO-8601 bounds; if omitted, no time bound is applied and the whole transcript is scanned, surfacing the most recent ERR/WARN lines. Severity is inclusive; start at WARN, never INFO. No raw noise ever enters the LLM context. |
| `check_os_resources` | `(service: str) -> OSReport` | Structured `df -h`, memory, and kernel alerts (`dmesg` ENOSPC/OOM). Read-only. |
| `analyze_crash_llm` | `(log_excerpt: str, topology: TopologyGraph, os_report: OSReport) -> RCAReport` | **Live Anthropic Messages API call**, Pydantic-structured output. `ANTHROPIC_API_KEY` + `DIAG_MCP_MODEL` env-configurable (`MCP_DIAG_MODEL` accepted as an alias); timeout + fail-closed error; schema *requires* timestamped verbatim citations, and `insufficient_evidence=True` when they are missing. |

All tools are **read-only by default**. Any fix ships as a dry-run command/diff and requires **Human-in-the-Loop** approval before execution.

### Skills & Sub-agents
* `SKILL.md` — deterministic 5-step workflow: (1) topology first, (2) parallel sub-agent dispatch, (3) isolate healthy branches, (4) timestamp correlation, (5) structured RCA with citations, surfacing unrelated findings as a separate cited list. Enforces the insufficient-evidence rule and HITL before any fix.
* `log-filter.md` — owns `fetch_service_logs`; outputs a compressed anomaly list with exact line citations.
* `config-auditor.md` — owns `check_os_resources`; read-only YAML/network config verification; never mutates.
* `CLAUDE.md` — read-only guardrails, citation format, HITL requirement.

---

## 4. Enterprise Readiness: Key Architectural Pillars
*Production target, not POC scope — the POC implements a thin slice of each.*

### A. Scalability (Handling Hundreds of Engineers & Services)
* **Stateless Web MCP:** The `streamable-http` MCP server is stateless and deployed behind a Kubernetes Load Balancer with horizontal auto-scaling.
* **Sub-Graph Retrieval (Graph DB):** In production, `get_service_topology()` queries a real-time Graph DB (**Neo4j**), retrieving only a 2–3 hop subgraph around the alerting component rather than loading massive static files.
* **Pre-LLM Filtering:** Deterministic filtering (deduplication, time-window slicing, severity filtering) runs in Python/Go inside the MCP server before data ever enters the LLM's context window.

### B. Real-World Enterprise Integration & Governance
* **Zero-Friction Distribution:** Shared `.mcp.json` configurations, `CLAUDE.md`, and `.claude/skills/` live directly in the R&D Git repositories. A standard `git pull` equips every engineer with the latest diagnostic workflows.
* **SSO & RBAC (Token Forwarding):** The centralized Web MCP server sits behind corporate SSO/OAuth. It forwards the engineer's identity token to downstream internal systems (K8s, lab managers, Jira), ensuring the agent strictly inherits the user's exact permissions.
* **Read-Only by Default:** All diagnostic tools execute with read-only privileges. State-mutating actions run in **Dry-Run** mode (generating a diff or CLI command) and enforce **Human-in-the-Loop (HITL)** approval.

### C. Extensibility (Self-Service for R&D Teams)
* **Decoupled Micro-MCP Servers:** Domain teams (Kernel, Networking, CI/CD, QA) own and deploy independent MCP servers (`lab-mcp`, `build-mcp`, `coredump-mcp`) adhering to strict Pydantic/JSON schemas.
* **Workflows as Code:** Teams author and version-control their own `SKILL.md` and sub-agent definitions via standard Pull Requests.
* **Distribution Model:** Each team repo ships its sub-agents (`.claude/agents/*.md` with `name`/`description`/`model`/`tools` frontmatter) *and* pins its server via scoped `.mcp.json`; the agent's `tools:` whitelist binds it to that server's namespace (`mcp__<server>__*`), so `git pull` distributes workflow and tools together. A `.claude-plugin` can bundle agents + skills + MCP config as one installable unit for an internal marketplace.
* **Preventing Tool Overload:** Repositories load only domain-relevant MCP servers via scoped `.mcp.json` files, while Sub-agents isolate specialized tools into separate context windows.

### D. Self-Monitoring & Continuous Improvement
* **Trajectory Tracing:** Every agent execution is logged via observability tools (**Langfuse** or Claude Code Hooks) to capture tool selection sequences, latencies, and token costs. Misdiagnoses are debugged by inspecting traces and refining tool docstrings or skill instructions.
* **Grounded Reasoning & Citations:** Output schemas mandate exact log timestamps and raw line citations for every claim. If evidence is missing, instructions force the agent to report *"Insufficient evidence"* rather than speculate.
* **Feedback Loop & Golden Dataset Evals:** Engineers rate diagnoses (👍/👎); failure cases are added to a versioned **Golden Dataset** of historical incidents. Any change to prompts, skills, or underlying models triggers automated regression tests (`Evals`) to verify diagnostic accuracy.

---

## 5. 4-Day Execution Plan

* **Day 1 – Environment & MCP Server:** Set up the `diag-mcp` repository, `CLAUDE.md`, `topology.json`, and the Dockerized `FastMCP` HTTP server. Verify tool discovery via `claude mcp list` and `/mcp`.
* **Day 2 – Mini-Lab & Fault Injection:** Create a lightweight `docker-compose.yml` (`api-gateway`, `routing-engine`, `telemetry-writer` with a `1MB tmpfs` mount) and trigger the cascading `ENOSPC` failure. *(Requires a Docker daemon; not runnable in restricted sandboxes.)* POC note: `demo_data/` holds the canonical fixtures instead.
* **Day 3 – Sub-agents & Skills:** Implement `.claude/skills/diagnose/SKILL.md`, `.claude/agents/log-filter.md`, and `.claude/agents/config-auditor.md` per the contracts in Section 3. Run end-to-end diagnostics against the canonical transcript (asserting the unrelated-findings path: the `auth-service` deploy line is reported as `unrelated`, not folded into the cascade), capture terminal traces, and refine failure modes.
* **Day 4 – Presentation Deck:** Build a concise 6–8 slide presentation covering the architecture, Claude Code development workflow, real failure-mode tuning, and enterprise rollout strategy.
