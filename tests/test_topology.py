"""Unit tests for get_service_topology."""

from __future__ import annotations

import pytest

from mcp_server.topology import get_service_topology


def test_full_subgraph_from_root(tmp_topology) -> None:
    g = get_service_topology("api-gateway", hops=2)
    names = {n.name for n in g.nodes}
    assert names == {"api-gateway", "auth-service", "routing-engine", "telemetry-writer", "nvme-tmpfs"}
    assert len(g.edges) == 4
    assert g.root == "api-gateway"


def test_hops_limits_depth(tmp_topology) -> None:
    g1 = get_service_topology("api-gateway", hops=1)
    assert {n.name for n in g1.nodes} == {"api-gateway", "auth-service", "routing-engine", "telemetry-writer"}
    assert ("telemetry-writer", "nvme-tmpfs") not in g1.edges


def test_zero_hops_returns_root_only(tmp_topology) -> None:
    g = get_service_topology("telemetry-writer", hops=0)
    assert [n.name for n in g.nodes] == ["telemetry-writer"]
    assert g.edges == []


def test_unknown_service_raises(tmp_topology) -> None:
    with pytest.raises(ValueError, match="unknown service"):
        get_service_topology("nope")


def test_hops_may_be_negative(tmp_topology) -> None:
    # max(hops, 0) guards it: behaves like 0 hops rather than exploding.
    g = get_service_topology("auth-service", hops=-3)
    assert [n.name for n in g.nodes] == ["auth-service"]
