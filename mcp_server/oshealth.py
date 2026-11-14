"""check_os_resources: structured disk/memory/kernel-alert report. Read-only."""

from __future__ import annotations

import json

from . import config
from .models import OSReport


def check_os_resources(service: str) -> OSReport:
    """Return df -h, memory, and kernel alerts (dmesg ENOSPC/OOM) for a service."""
    with open(config.OS_PATH, "r", encoding="utf-8") as f:
        data: dict = json.load(f)

    if service not in data:
        raise ValueError(f"unknown service: {service!r}")

    report = data[service]
    return OSReport(
        service=service,
        disk=report["disk"],
        memory=report["memory"],
        kernel_alerts=report["kernel_alerts"],
    )
