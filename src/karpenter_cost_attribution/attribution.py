"""Allocate each node's hourly cost across the namespaces of pods
scheduled on it, proportional to CPU request share.

Memory-proportional allocation is left as a documented alternative rather
than blended in by default, since CPU is the more common bin-packing
driver for Karpenter consolidation decisions.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from karpenter_cost_attribution.k8s_client import NodeInfo
from karpenter_cost_attribution.pricing import get_hourly_rate


def allocate_costs(
    nodes: list[NodeInfo],
    namespace_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return per-namespace hourly cost, sorted highest first.

    namespace_filter supports a simple trailing-wildcard prefix match
    (e.g. "team-*"); anything more complex should filter downstream.
    """
    namespace_hourly_cost: dict[str, float] = defaultdict(float)

    for node in nodes:
        hourly_rate = get_hourly_rate(node.instance_type, node.capacity_type)
        total_cpu = sum(p.cpu_request_millicores for p in node.pods) or 1

        for pod in node.pods:
            share = pod.cpu_request_millicores / total_cpu
            namespace_hourly_cost[pod.namespace] += hourly_rate * share

    rows = [
        {"namespace": ns, "hourly_cost": round(cost, 4), "monthly_estimate": round(cost * 730, 2)}
        for ns, cost in namespace_hourly_cost.items()
    ]

    if namespace_filter and namespace_filter.endswith("*"):
        prefix = namespace_filter[:-1]
        rows = [r for r in rows if r["namespace"].startswith(prefix)]

    rows.sort(key=lambda r: r["monthly_estimate"], reverse=True)
    return rows
