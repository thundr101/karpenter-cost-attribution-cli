"""Command-line entrypoint: `karpenter-cost-attribution report ...`"""
from __future__ import annotations

import argparse

from karpenter_cost_attribution.attribution import allocate_costs
from karpenter_cost_attribution.k8s_client import load_cluster_state
from karpenter_cost_attribution.report import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="karpenter-cost-attribution")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="Report cost attribution by namespace")
    report.add_argument("--kube-context", type=str, default=None)
    report.add_argument("--namespace-filter", type=str, default=None, help="e.g. 'team-*'")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        nodes = load_cluster_state(kube_context=args.kube_context)
        rows = allocate_costs(nodes, namespace_filter=args.namespace_filter)
        print(render_markdown(rows))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
