"""Command-line entrypoint: `karpenter-cost-attribution report ...`"""

from __future__ import annotations

import argparse

from karpenter_cost_attribution.attribution import allocate_costs
from karpenter_cost_attribution.k8s_client import load_cluster_state
from karpenter_cost_attribution.report import render_markdown, render_chart


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="karpenter-cost-attribution")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="Report cost attribution by namespace")
    report.add_argument("--kube-context", type=str, default=None)
    report.add_argument("--namespace-filter", type=str, default=None, help="e.g. 'team-*'")
    report.add_argument(
        "--output-chart", type=str, default=None, help="Path to save the cost breakdown PNG chart"
    )
    report.add_argument(
        "--aws-region", type=str, default="us-east-1", help="AWS Region (default: us-east-1)"
    )
    report.add_argument(
        "--aws-profile", type=str, default=None, help="AWS CLI Profile (default: None)"
    )
    report.add_argument(
        "--refresh-cache", action="store_true", help="Force refresh cached pricing data"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        nodes = load_cluster_state(kube_context=args.kube_context)
        rows = allocate_costs(
            nodes,
            namespace_filter=args.namespace_filter,
            aws_region=args.aws_region,
            aws_profile=args.aws_profile,
            refresh_cache=args.refresh_cache,
        )
        print(render_markdown(rows))

        if args.output_chart:
            render_chart(rows, args.output_chart)
            print(f"Chart saved to {args.output_chart}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
