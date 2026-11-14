"""get_service_topology: deterministic graph read from topology.yaml.

POC reads the YAML file; production swaps this for a Neo4j 2-3 hop subgraph query.
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from . import config
from .models import TopologyGraph, TopologyNode


@lru_cache(maxsize=1)
def _load_topology(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_service_topology(service: str, hops: int = 2) -> TopologyGraph:
    """Return the dependency subgraph around `service`, up to `hops` edges deep.

    POC source: topology.yaml. Production source: Neo4j subgraph query.
    """
    data = _load_topology(config.TOPOLOGY_PATH)
    services: dict = data["services"]

    if service not in services:
        raise ValueError(f"unknown service: {service!r}")

    nodes: dict[str, TopologyNode] = {}
    edges: list[tuple[str, str]] = []
    frontier = [service]
    seen = {service}

    for _ in range(max(hops, 0)):
        next_frontier: list[str] = []
        for name in frontier:
            node = services[name]
            nodes.setdefault(
                name,
                TopologyNode(name=name, kind=node.get("kind", "service"),
                             notes=node.get("notes", ""),
                             downstream=list(node.get("downstream", []))),
            )
            for dep in node.get("downstream", []):
                edges.append((name, dep))
                if dep in services and dep not in seen:
                    seen.add(dep)
                    next_frontier.append(dep)
        frontier = next_frontier

    # Include leaf nodes reachable exactly at the hop boundary (no further expansion).
    for name in frontier:
        if name not in nodes:
            node = services[name]
            nodes[name] = TopologyNode(name=name, kind=node.get("kind", "service"),
                                       notes=node.get("notes", ""),
                                       downstream=list(node.get("downstream", [])))

    return TopologyGraph(root=service, nodes=list(nodes.values()), edges=edges)
