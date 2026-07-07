"""Discover node -> pod -> namespace mapping from the live cluster.

Uses the ambient kubeconfig context (whatever `kubectl` is currently
pointed at) rather than requiring cluster credentials to be re-specified.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from kubernetes import client, config


@dataclass
class PodAllocation:
    namespace: str
    cpu_request_millicores: int
    memory_request_mib: int


@dataclass
class NodeInfo:
    name: str
    instance_type: str
    capacity_type: str  # "on-demand" | "spot"
    pods: list[PodAllocation] = field(default_factory=list)


def load_cluster_state(kube_context: str | None = None) -> list[NodeInfo]:
    """Return NodeInfo for every Karpenter-provisioned node with its
    currently scheduled pods and their resource requests.

    TODO: paginate pod listing for very large clusters (list_pod_for_all_namespaces
    supports `limit`/`_continue`, not wired up yet).
    """
    if kube_context:
        config.load_kube_config(context=kube_context)
    else:
        config.load_kube_config()

    core = client.CoreV1Api()

    nodes: dict[str, NodeInfo] = {}
    for node in core.list_node().items:
        labels = node.metadata.labels or {}
        if "karpenter.sh/nodepool" not in labels:
            continue  # only interested in Karpenter-managed nodes

        nodes[node.metadata.name] = NodeInfo(
            name=node.metadata.name,
            instance_type=labels.get("node.kubernetes.io/instance-type", "unknown"),
            capacity_type=labels.get("karpenter.sh/capacity-type", "on-demand"),
        )

    for pod in core.list_pod_for_all_namespaces().items:
        node_name = pod.spec.node_name
        if node_name not in nodes:
            continue

        cpu_millicores = 0
        mem_mib = 0
        for container in pod.spec.containers:
            requests = (container.resources.requests or {}) if container.resources else {}
            cpu_millicores += _parse_cpu(requests.get("cpu", "0"))
            mem_mib += _parse_memory(requests.get("memory", "0"))

        nodes[node_name].pods.append(
            PodAllocation(
                namespace=pod.metadata.namespace,
                cpu_request_millicores=cpu_millicores,
                memory_request_mib=mem_mib,
            )
        )

    return list(nodes.values())


def _parse_cpu(value: str) -> int:
    """Parse Kubernetes CPU quantity strings ('500m', '1', '2.5') to millicores."""
    if value.endswith("m"):
        return int(value[:-1])
    return int(float(value) * 1000)


def _parse_memory(value: str) -> int:
    """Parse Kubernetes memory quantity strings ('512Mi', '1Gi') to MiB.

    TODO: handle decimal SI units (e.g. '1G', '500M') — currently only
    binary Ki/Mi/Gi suffixes are supported.
    """
    if value.endswith("Mi"):
        return int(value[:-2])
    if value.endswith("Gi"):
        return int(float(value[:-2]) * 1024)
    if value.endswith("Ki"):
        return max(1, int(value[:-2]) // 1024)
    return 0
