---
name: diagnose
description: Topology-aware root-cause analysis for a service incident. Use when the user reports an outage, error spike, latency anomaly, or asks "what's broken" / "why is X failing". Runs the four mcp__diag-mcp__* tools in order and produces a cited RCAReport.
---

# diagnose — topology-aware RCA workflow

Deterministic 5-step RCA. **Read-only by default**: never write, delete, restart, or
apply anything. Every claim in the final report needs a verbatim log line + UTC
timestamp. A claim without one is speculation — report `insufficient_evidence=true`
instead of guessing. Fixes are proposed as dry-run commands only; executing any fix
requires explicit human approval (HITL), always.

## Inputs to ask for

- `service` — the alerting component (e.g. `api-gateway`).
- `since` / `until` — UTC ISO-8601 window with millisecond precision
  (e.g. `2026-11-14T10:00:00.000Z`). Default to the last hour if unsure.

## Step 1 — Topology first

`mcp__diag-mcp__get_service_topology(service, hops=2)`

Map every downstream dependency before touching logs. Do not skip this — the topology
decides which branches to inspect in parallel in Step 2.

## Step 2 — Dispatch sub-agents in parallel

For **every** node in the topology graph:

- `.claude/agents/log-filter.md` (`log-filter`) — owns `fetch_service_logs` for that
  node; returns a compressed anomaly list with exact line citations.
- `.claude/agents/config-auditor.md` (`config-auditor`) — owns `check_os_resources`
  for that node; returns disk/memory/kernel-alert state. Read-only.

Both run per-node, in parallel, with the same `since`/`until` window.

## Step 3 — Isolate healthy branches

From the sub-agent outputs, separate:

- **Healthy** nodes: no WARN/ERROR, disk ok, no kernel alerts.
- **Impacted** nodes: symptoms present, but OS level healthy (symptom, not cause).
- **Root-cause candidate**: the node where an OS-level fault (ENOSPC, OOM, disk 100%)
  precedes every downstream symptom in time.

Decoys are real log lines that are *not* the cause — a deploy completing, a GC pause
within SLO, retransmits that are themselves a symptom. Mark them `excluded`, cite
them, never fold them into the chain.

## Step 4 — Correlate timestamps

All timestamps are UTC ISO-8601 with millisecond precision on NTP-synced hosts, so
the propagation delay between two events is plain timestamp subtraction. Order the
cascade: root cause → propagation → symptom. Build the `timeline` with each step's
`t_offset_ms` relative to the root-cause timestamp.

## Step 5 — Structured RCA with citations

Assemble the `RCAReport` and call `mcp__diag-mcp__analyze_crash_llm(log_excerpt,
topology, os_report)` with the root-cause candidate's data. Validate the returned
report against the schema:

- `evidence[].role` is one of `root_cause` | `propagation` | `symptom` | `excluded` |
  `unrelated`.
- `unrelated_findings` holds real, cited issues that do **not** correlate with this
  cascade (e.g. an unrelated deploy line). Never fold them into `root_cause`.
- `fix.requires_hitl_approval` is `true`; `fix.dry_run_command` is a command, never an
  executed action.
- `confidence` in [0, 1]; `insufficient_evidence` is `true` when citations are missing.

## Output

Return the RCAReport verbatim to the user, plus a one-line summary of the cascade
ordering and the unrelated findings listed separately. If `insufficient_evidence` is
true, say so and say exactly which citations are missing — do not improvise them.

## Reference

Full contracts: `mcp-diag-blueprint.md` Section 3. Canonical demo transcript:
`demo_data/logs.jsonl` (ENOSPC on `telemetry-writer` → 503 → gateway pool exhausted →
client retry storm; `auth-service` deploy line is the unrelated finding).
