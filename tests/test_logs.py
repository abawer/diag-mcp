"""Unit tests for fetch_service_logs and the dedup key."""

from __future__ import annotations

import json

import pytest

from mcp_server import config
from mcp_server.logs import _fingerprint, fetch_service_logs
from mcp_server.models import LogLine

SINCE = "2026-11-14T10:00:00.000Z"
UNTIL = "2026-11-14T10:00:01.000Z"


def test_window_and_severity_filter(tmp_logs, log_lines) -> None:
    got = fetch_service_logs("telemetry-writer", since=SINCE, until=UNTIL)
    assert len(got) == 2  # ENOSPC ERROR + 503 WARN; INFO-level lines excluded by default


def test_default_severity_warn_excludes_info(tmp_logs) -> None:
    rows = [{"timestamp": "2026-11-14T10:00:00.100Z", "service": "auth-service", "level": "INFO",
             "line": "[deploy] rolling deploy v2.4.1 complete (canary=100%)"}]
    with open(tmp_logs, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    got = fetch_service_logs("auth-service", since=SINCE, until=UNTIL)
    assert got == []  # INFO < default WARN gate


def test_severity_debug_admits_info(tmp_logs) -> None:
    got = fetch_service_logs("auth-service", since=SINCE, until=UNTIL, severity="DEBUG")
    assert len(got) == 1 and got[0].level == "INFO"


def test_regex_filter(tmp_logs) -> None:
    got = fetch_service_logs("telemetry-writer", since=SINCE, until=UNTIL, severity="DEBUG",
                             regex_filter=r"ENOSPC")
    assert len(got) == 1 and "ENOSPC" in got[0].line


def test_regex_filter_excludes_non_matching(tmp_logs) -> None:
    got = fetch_service_logs("telemetry-writer", since=SINCE, until=UNTIL, severity="DEBUG",
                             regex_filter=r"^\[http\]")
    assert len(got) == 1 and got[0].line.startswith("[http]")


def test_limit_caps_results(tmp_logs, log_lines) -> None:
    got = fetch_service_logs("telemetry-writer", since=SINCE, until=UNTIL, severity="DEBUG", limit=1)
    assert len(got) == 1


def test_dedup_collapses_exact_repeats(tmp_logs) -> None:
    dup = {"timestamp": "2026-11-14T10:00:00.500Z", "service": "telemetry-writer", "level": "ERROR",
           "line": "[disk] ENOSPC: No space left on device writing /metrics/2026-11-14.bin (tmpfs 1MB cap)"}
    with open(tmp_logs, "a") as f:
        f.write(json.dumps(dup) + "\n")
    got = fetch_service_logs("telemetry-writer", since=SINCE, until=UNTIL, severity="DEBUG")
    # 3 distinct contents (ENOSPC, 503, + duplicate ENOSPC) -> still 2
    assert len(got) == 2


def test_dedup_keeps_distinct_ids(tmp_path, monkeypatch) -> None:
    """Two different request IDs are two different failures — no template collapsing."""
    rows = [
        {"timestamp": "2026-11-14T10:00:00.000Z", "service": "api-gateway", "level": "ERROR",
         "line": "[http] req id-1 failed"},
        {"timestamp": "2026-11-14T10:00:00.100Z", "service": "api-gateway", "level": "ERROR",
         "line": "[http] req id-2 failed"},
    ]
    path = tmp_path / "logs.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    monkeypatch.setattr(config, "LOGS_PATH", str(path))
    got = fetch_service_logs("api-gateway", since=SINCE, until=UNTIL, severity="DEBUG")
    assert len(got) == 2


def test_fingerprint_excludes_timestamp(tmp_logs) -> None:
    a = LogLine(timestamp="2026-11-14T10:00:00.000Z", service="s", level="ERROR", line="boom")
    b = LogLine(timestamp="2026-11-14T10:00:05.000Z", service="s", level="ERROR", line="boom")
    assert _fingerprint(a) == _fingerprint(b)


def test_fingerprint_distinguishes_level_and_content(tmp_logs) -> None:
    a = LogLine(timestamp="t", service="s", level="ERROR", line="boom")
    b = LogLine(timestamp="t", service="s", level="WARN", line="boom")
    c = LogLine(timestamp="t", service="s", level="ERROR", line="bam")
    assert _fingerprint(a) != _fingerprint(b)
    assert _fingerprint(a) != _fingerprint(c)


def test_unknown_service_returns_empty(tmp_logs) -> None:
    assert fetch_service_logs("ghost", since=SINCE, until=UNTIL) == []


def test_empty_window_returns_empty(tmp_logs) -> None:
    got = fetch_service_logs("telemetry-writer", since="2025-01-01T00:00:00.000Z",
                             until="2025-01-02T00:00:00.000Z")
    assert got == []


def test_omitted_window_scans_whole_transcript(tmp_logs) -> None:
    """No since/until: the severity gate still surfaces the most recent ERR/WARN lines."""
    got = fetch_service_logs("telemetry-writer", severity="DEBUG")
    assert len(got) == 2  # ENOSPC ERROR + 503 WARN — full transcript, no time bound


def test_since_only_bounds_the_past(tmp_logs) -> None:
    got = fetch_service_logs("telemetry-writer", since="2026-11-14T10:00:00.001Z", severity="DEBUG")
    assert len(got) == 1 and got[0].level == "WARN"


def test_until_only_bounds_the_future(tmp_logs) -> None:
    got = fetch_service_logs("telemetry-writer", until="2026-11-14T10:00:00.001Z", severity="DEBUG")
    assert len(got) == 1 and got[0].level == "ERROR"


def test_omitted_window_returns_most_recent_err_warn(tmp_logs) -> None:
    """Default severity gate + no window: newest ERROR/WARN across the transcript."""
    got = fetch_service_logs("api-gateway")
    assert len(got) == 1 and "worker pool exhausted" in got[0].line
