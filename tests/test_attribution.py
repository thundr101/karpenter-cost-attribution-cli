from karpenter_cost_attribution.attribution import allocate_costs
from karpenter_cost_attribution.k8s_client import NodeInfo, PodAllocation


def test_single_namespace_gets_full_node_cost():
    node = NodeInfo(
        name="node-1",
        instance_type="m5.large",
        capacity_type="on-demand",
        pods=[
            PodAllocation(namespace="team-a", cpu_request_millicores=1000, memory_request_mib=512)
        ],
    )
    rows = allocate_costs([node])
    assert len(rows) == 1
    assert rows[0]["namespace"] == "team-a"
    assert rows[0]["hourly_cost"] > 0


def test_two_namespaces_split_proportionally():
    node = NodeInfo(
        name="node-1",
        instance_type="m5.large",
        capacity_type="on-demand",
        pods=[
            PodAllocation(namespace="team-a", cpu_request_millicores=750, memory_request_mib=512),
            PodAllocation(namespace="team-b", cpu_request_millicores=250, memory_request_mib=256),
        ],
    )
    rows = allocate_costs([node])
    by_ns = {r["namespace"]: r["hourly_cost"] for r in rows}
    assert by_ns["team-a"] > by_ns["team-b"]


def test_namespace_filter_wildcard():
    node = NodeInfo(
        name="node-1",
        instance_type="m5.large",
        capacity_type="on-demand",
        pods=[
            PodAllocation(namespace="team-a", cpu_request_millicores=500, memory_request_mib=256),
            PodAllocation(
                namespace="kube-system", cpu_request_millicores=500, memory_request_mib=256
            ),
        ],
    )
    rows = allocate_costs([node], namespace_filter="team-*")
    assert all(r["namespace"].startswith("team-") for r in rows)
