"""Render per-namespace cost attribution as a markdown table."""
from __future__ import annotations

from typing import Any


def render_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "## Karpenter Cost Attribution\n\nNo Karpenter-managed nodes found.\n"

    lines = ["## Karpenter Cost Attribution by Namespace\n"]
    lines.append("| Namespace | Hourly Cost | Monthly Estimate |")
    lines.append("|---|---|---|")
    for r in rows:
        lines.append(f"| {r['namespace']} | ${r['hourly_cost']:.4f} | ${r['monthly_estimate']:.2f} |")
    return "\n".join(lines) + "\n"
