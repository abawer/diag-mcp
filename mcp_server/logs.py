"""fetch_service_logs: deterministic pre-LLM filtering.

Pipeline: time-window slice -> severity gate -> regex match -> dedup on exact
content (timestamp excluded) -> hard line cap. No raw noise enters the LLM context.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime

from . import config
from .models import LogLine

SEVERITY_ORDER = {
    "DEBUG": 0,
    "INFO": 1,
    "WARN": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}


def _parse_ts(ts: str) -> datetime:
    # Accepts 2026-11-14T10:00:00.005Z
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _fingerprint(entry: LogLine) -> tuple:
    """Dedup key: exact log content with the timestamp excluded.

    Deliberately plain — no template collapsing. Two requests failing with
    different IDs can have different root causes; masking the IDs into one
    template would hide that. Our JSONL schema keeps the timestamp in its own
    field, so `line` is already TS-free: nothing to split, nothing to hash —
    a plain tuple is hashable and serves as the key.
    """
    return (entry.level, entry.line)


def _load_all() -> list[LogLine]:
    out: list[LogLine] = []
    with open(config.LOGS_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            out.append(LogLine(timestamp=rec["timestamp"], service=rec["service"],
                               level=rec["level"], line=rec["line"]))
    return out


def fetch_service_logs(
    service: str,
    since: str,
    until: str,
    severity: str = "WARN",
    regex_filter: str | None = None,
    limit: int = 200,
) -> list[LogLine]:
    """Return filtered logs for one service within a UTC window."""
    since_dt, until_dt = _parse_ts(since), _parse_ts(until)
    min_sev = SEVERITY_ORDER[severity.upper()]
    pattern = re.compile(regex_filter) if regex_filter else None

    dedup: "OrderedDict[tuple, LogLine]" = OrderedDict()
    for entry in _load_all():
        if entry.service != service:
            continue
        ts = _parse_ts(entry.timestamp)
        if ts < since_dt or ts > until_dt:
            continue
        if SEVERITY_ORDER[entry.level.upper()] < min_sev:
            continue
        if pattern and not pattern.search(entry.line):
            continue
        fp = _fingerprint(entry)
        if fp not in dedup:
            dedup[fp] = entry

    return list(dedup.values())[:limit]
