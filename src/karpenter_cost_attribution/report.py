"""Render per-namespace cost attribution as a markdown table or visual chart."""

from __future__ import annotations

from typing import Any


def render_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "## Karpenter Cost Attribution\n\nNo Karpenter-managed nodes found.\n"

    lines = ["## Karpenter Cost Attribution by Namespace\n"]
    lines.append("| Namespace | Hourly Cost | Monthly Estimate |")
    lines.append("|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['namespace']} | ${r['hourly_cost']:.4f} | ${r['monthly_estimate']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def render_chart(rows: list[dict[str, Any]], output_path: str) -> None:
    """Render a premium-looking cost breakdown chart and save it as a PNG."""
    import matplotlib.pyplot as plt
    import numpy as np

    if not rows:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "No Karpenter-managed nodes found.",
            ha="center",
            va="center",
            fontsize=12,
            color="gray",
        )
        ax.axis("off")
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()
        return

    # Sort rows by monthly estimate ascending so the highest is at the top when plotted horizontally
    sorted_rows = sorted(rows, key=lambda x: x["monthly_estimate"])
    namespaces = [r["namespace"] for r in sorted_rows]
    monthly_costs = [r["monthly_estimate"] for r in sorted_rows]
    total_cost = sum(monthly_costs)

    # Set up dark modern style
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor("#0f172a")  # Tailwind slate-900 background
    ax.set_facecolor("#0f172a")

    # Color palette - gradient from deep violet to vibrant teal/cyan
    colors = plt.cm.viridis(np.linspace(0.3, 0.85, len(sorted_rows)))

    bars = ax.barh(namespaces, monthly_costs, color=colors, edgecolor="none", height=0.6)

    # Styling spines
    for spine in ["top", "right", "bottom", "left"]:
        ax.spines[spine].set_visible(False)

    # Style grid
    ax.xaxis.grid(True, linestyle="--", alpha=0.15, color="#cbd5e1")
    ax.set_axisbelow(True)

    # Add text labels inside or at the end of the bars
    for bar, val in zip(bars, monthly_costs):
        width = bar.get_width()
        pct = (val / total_cost * 100) if total_cost > 0 else 0
        label_text = f" ${val:,.2f} ({pct:.1f}%)"
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            label_text,
            va="center",
            ha="left",
            fontsize=9,
            fontweight="semibold",
            color="#e2e8f0",
        )

    # Style labels & title
    ax.set_title(
        "Karpenter Cost Attribution by Namespace",
        fontsize=14,
        fontweight="bold",
        pad=20,
        color="#f8fafc",
    )
    ax.set_xlabel("Estimated Monthly Cost ($)", fontsize=10, labelpad=10, color="#94a3b8")
    ax.tick_params(axis="both", colors="#94a3b8", labelsize=10)

    # Adjust layout to fit labels nicely
    plt.tight_layout()
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none", dpi=300)
    plt.close()
