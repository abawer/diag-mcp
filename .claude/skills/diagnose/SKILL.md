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
- `since` / `until` — optional UTC ISO-8601 window bounds with millisecond
  precision (e.g. `2026-11-14T10:00:00.000Z`). If the caller did not give a
  window, omit them: the tool then scans the whole transcript and returns the
  most recent ERR/WARN lines. Never invent a window yourself.

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

Both run per-node, in parallel, with the same `since`/`until` window — or both
unbounded when the caller gave no window.

**Severity gate (critical):** the severity filter is inclusive — `severity="INFO"`
drops every WARN/ERROR line, which is exactly where anomalies live. Always dispatch
log-filter with `severity="WARN"` (or have it start at WARN), never INFO. If WARN
returns nothing, re-run at INFO to check for boundary-establishing INFO lines only.
An empty `kept` list with known traffic is a wrong-severity symptom, not a healthy
node.

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

All timestamps are UTC ISO-8601 with millisecond precision on NTP-synced hosts.
Order the cascade (root cause → propagation → symptom) by comparing the **raw
timestamp strings** as they appear in the log lines. Do not compute deltas, offsets,
or durations, and do not derive any time value the logs do not literally contain —
the transcript has no Δ field, so inventing one is fabrication. Build the `timeline`
using each event's verbatim `timestamp` value, untouched.

## Step 5 — Structured RCA with citations

Assemble the `RCAReport` and call `mcp__diag-mcp__analyze_crash_llm(log_excerpt,
topology, os_report)` with the root-cause candidate's data. Validate the returned
report against the schema:

- `evidence[].role` is one of `root_cause` | `propagation` | `symptom` | `excluded` |
  `unrelated`. Every `timestamp` is copied verbatim from the log line — never derived.
- `timeline[]` entries carry `timestamp` (verbatim), `service`, `event`. No
  `t_offset_ms` field exists; offsets are never computed or emitted.
- `unrelated_findings` holds real, cited issues that do **not** correlate with this
  cascade (e.g. an unrelated deploy line). Never fold them into `root_cause`.
- `fix.requires_hitl_approval` is `true`; `fix.dry_run_command` is a command, never an
  executed action.
- `confidence` in [0, 1]; `insufficient_evidence` is `true` when citations are missing.

## Output

Return the RCAReport verbatim to the user, plus a one-line summary of the cascade
ordering and the unrelated findings listed separately. If `insufficient_evidence` is
true, say so and say exactly which citations are missing — do not improvise them.
Every timestamp in the report is a raw value copied from a log line. No deltas,
offsets, durations, or `t_offset_ms` anywhere — not even in prose.

## Scope

Run Steps 1–5 and stop. Do not read any other file, do not follow pointers to design
docs or plans, and do not execute any other workflow (including blueprint day plans,
presentation decks, or repo setup steps). The only inputs to this skill are the four
`mcp__diag-mcp__*` tools and the service/window you were given.
