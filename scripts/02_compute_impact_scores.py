"""Phase 2: Compute Parking Impact Scores + Advanced EDA.

Usage:
    python scripts/02_compute_impact_scores.py

This script runs the full Phase 2 pipeline:
    1. Load enriched violations from Phase 1
    2. Compute PIS (6 components → 0-100 score)
    3. Add economic cost + carbon impact
    4. Run weight sensitivity analysis
    5. Learn data-driven weights via Random Forest
    6. Run HDBSCAN clustering
    7. Update parquet with PIS + cluster_id + costs
    8. Generate 15+ research visualizations
    9. Save research report

Reference: plans/phase2_impact_scoring.md
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from drishtam.clustering import (
    characterize_clusters,
    cluster_violations,
    rank_enforcement_zones,
)
from drishtam.config import (
    ENRICHED_DATA_PATH,
    EVENT_PATH,
    PIS_BAND_COLORS,
    PIS_WEIGHTS,
    PLOT_DPI,
    RESEARCH_DIR,
    setup_logging,
)
from drishtam.impact_scorer import (
    compute_carbon_impact,
    compute_economic_cost,
    compute_pis,
    learn_optimal_weights,
    weight_sensitivity_analysis,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VISUALIZATIONS (15+ charts)
# =============================================================================


def generate_pis_visualizations(
    df: pd.DataFrame,
    cluster_stats: pd.DataFrame,
    weight_results: dict,
    output_dir: Path,
) -> None:
    """Generate all Phase 2 visualizations."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_style("darkgrid")
    plt.rcParams.update({"figure.dpi": PLOT_DPI, "savefig.dpi": PLOT_DPI, "font.size": 10})

    # === Chart 1: PIS Distribution ===
    logger.info("Chart 1: PIS Distribution")
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.hist(df["pis"], bins=100, color="#ff6600", edgecolor="white", alpha=0.8)
    ax.axvline(df["pis"].mean(), color="red", linestyle="--", linewidth=2, label=f"Mean: {df['pis'].mean():.1f}")
    ax.axvline(df["pis"].median(), color="blue", linestyle="--", linewidth=2, label=f"Median: {df['pis'].median():.1f}")
    for low, high, name in [(0, 20, "LOW"), (20, 40, "MOD"), (40, 60, "HIGH"), (60, 80, "SEV"), (80, 100, "CRIT")]:
        ax.axvline(high, color="gray", linestyle=":", alpha=0.5)
        ax.text(low + (high - low) / 2, ax.get_ylim()[1] * 0.95, name, ha="center", fontsize=8, alpha=0.7)
    ax.set_xlabel("Parking Impact Score (PIS)")
    ax.set_ylabel("Count")
    ax.set_title("PIS Distribution — 298K Parking Violations", fontsize=14, fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_distribution.png")
    plt.close(fig)

    # === Chart 2: PIS by Road Tier ===
    logger.info("Chart 2: PIS by Road Tier")
    fig, ax = plt.subplots(figsize=(14, 7))
    tier_order = df.groupby("road_tier_name")["pis"].median().sort_values(ascending=False).index
    sns.boxplot(data=df, x="road_tier_name", y="pis", order=tier_order, ax=ax, palette="YlOrRd", showfliers=False)
    ax.set_xlabel("Road Tier")
    ax.set_ylabel("PIS")
    ax.set_title("PIS Distribution by Road Tier", fontsize=14, fontweight="bold")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_by_road_tier.png")
    plt.close(fig)

    # === Chart 3: PIS Spatial Map ===
    logger.info("Chart 3: PIS Spatial Map")
    fig, ax = plt.subplots(figsize=(14, 12))
    sample = df.sample(min(50000, len(df)), random_state=42)
    scatter = ax.scatter(
        sample["longitude"],
        sample["latitude"],
        c=sample["pis"],
        cmap="YlOrRd",
        s=1,
        alpha=0.5,
        vmin=0,
        vmax=80,
    )
    plt.colorbar(scatter, ax=ax, label="PIS Score", shrink=0.8)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Bengaluru — Violations by PIS Score", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_spatial_map.png")
    plt.close(fig)

    # === Chart 4: PIS vs Capacity Blocked ===
    logger.info("Chart 4: PIS vs Capacity Blocked")
    fig, ax = plt.subplots(figsize=(10, 8))
    sample = df.sample(min(10000, len(df)), random_state=42)
    ax.scatter(sample["capacity_blocked_pct"], sample["pis"], s=2, alpha=0.3, color="#ff6600")
    ax.set_xlabel("Capacity Blocked (%)")
    ax.set_ylabel("PIS Score")
    ax.set_title("PIS vs Capacity Blocked — PIS Captures More Nuance", fontsize=14, fontweight="bold")
    z = np.polyfit(sample["capacity_blocked_pct"], sample["pis"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(0, 100, 100)
    ax.plot(
        x_line,
        p(x_line),
        "r--",
        linewidth=2,
        label=f"Trend (r={sample['capacity_blocked_pct'].corr(sample['pis']):.2f})",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_vs_capacity.png")
    plt.close(fig)

    # === Chart 5: PIS Component Breakdown (Top 20 violations) ===
    logger.info("Chart 5: PIS Component Breakdown")
    top20 = df.nlargest(20, "pis")
    component_cols = ["pis_capacity", "pis_importance", "pis_junction", "pis_temporal", "pis_density", "pis_severity"]
    fig, ax = plt.subplots(figsize=(16, 8))
    bottom = np.zeros(20)
    colors = ["#ff4444", "#ff8800", "#ffcc00", "#44aaff", "#00cc66", "#cc44ff"]
    labels = ["Capacity", "Importance", "Junction", "Temporal", "Density", "Severity"]
    for col, color, label in zip(component_cols, colors, labels, strict=True):
        values = top20[col].values
        ax.barh(range(20), values, left=bottom, color=color, label=label, edgecolor="white", linewidth=0.5)
        bottom += values
    ax.set_yticks(range(20))
    ax.set_yticklabels([f"#{i + 1} (PIS={pis:.0f})" for i, pis in enumerate(top20["pis"].values)])
    ax.set_xlabel("Component Score (0-1 each)")
    ax.set_title("PIS Component Breakdown — Top 20 Highest-Impact Violations", fontsize=14, fontweight="bold")
    ax.legend(loc="lower right")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_component_breakdown.png")
    plt.close(fig)

    # === Chart 6: PIS Temporal Pattern ===
    logger.info("Chart 6: PIS Temporal Pattern")
    fig, ax1 = plt.subplots(figsize=(14, 6))
    hourly = df.groupby("hour_ist").agg(count=("pis", "count"), mean_pis=("pis", "mean"))
    ax1.bar(hourly.index, hourly["count"], color="#cccccc", alpha=0.7, label="Violation Count")
    ax1.set_xlabel("Hour (IST)")
    ax1.set_ylabel("Violation Count", color="gray")
    ax2 = ax1.twinx()
    ax2.plot(hourly.index, hourly["mean_pis"], color="#ff0000", linewidth=3, marker="o", markersize=5, label="Mean PIS")
    ax2.set_ylabel("Mean PIS", color="red")
    ax1.axvspan(8, 10, alpha=0.1, color="red")
    ax1.axvspan(17, 20, alpha=0.1, color="orange")
    ax1.set_title("PIS Temporal Pattern — Mean PIS Peaks at Rush Hours", fontsize=14, fontweight="bold")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_xticks(range(24))
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_temporal_pattern.png")
    plt.close(fig)

    # === Chart 7: Top 20 Roads by Mean PIS ===
    logger.info("Chart 7: Top 20 Roads by Mean PIS")
    road_stats = df.groupby("road_name").agg(mean_pis=("pis", "mean"), count=("pis", "count"))
    road_stats = road_stats[road_stats["count"] >= 20].sort_values("mean_pis", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(14, 8))
    colors = [
        PIS_BAND_COLORS.get("CRITICAL" if v > 60 else "SEVERE" if v > 40 else "HIGH", "#ff6600")
        for v in road_stats["mean_pis"]
    ]
    bars = ax.barh(range(len(road_stats)), road_stats["mean_pis"], color=colors, edgecolor="white")
    ax.set_yticks(range(len(road_stats)))
    ax.set_yticklabels([f"{name} (n={cnt})" for name, cnt in zip(road_stats.index, road_stats["count"], strict=True)])
    ax.set_xlabel("Mean PIS")
    ax.set_title("Top 20 Roads by Mean Parking Impact Score", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    for bar, val in zip(bars, road_stats["mean_pis"], strict=True):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2, f"{val:.1f}", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_top_roads.png")
    plt.close(fig)

    # === Chart 8: Pareto Chart ===
    logger.info("Chart 8: Pareto Chart")
    sorted_pis = df["pis"].sort_values(ascending=False).values
    cumulative = np.cumsum(sorted_pis) / sorted_pis.sum() * 100
    pct_violations = np.arange(1, len(sorted_pis) + 1) / len(sorted_pis) * 100
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(pct_violations, cumulative, color="#ff0000", linewidth=2)
    ax.axhline(80, color="gray", linestyle="--", alpha=0.7)
    idx_80 = np.searchsorted(cumulative, 80)
    pct_at_80 = pct_violations[idx_80]
    ax.axvline(pct_at_80, color="blue", linestyle="--", alpha=0.7)
    ax.fill_between(pct_violations[:idx_80], cumulative[:idx_80], alpha=0.2, color="red")
    ax.text(pct_at_80 + 2, 82, f"Top {pct_at_80:.0f}% → 80% of impact", fontsize=12, color="blue")
    ax.set_xlabel("% of Violations (sorted by PIS)")
    ax.set_ylabel("% of Total Impact (cumulative PIS)")
    ax.set_title("Pareto Analysis — Impact Concentration", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_pareto.png")
    plt.close(fig)

    # === Chart 9: Enforcement Gap ===
    logger.info("Chart 9: Enforcement Gap Analysis")
    fig, ax1 = plt.subplots(figsize=(14, 6))
    hourly_detail = df.groupby("hour_ist").agg(
        count=("pis", "count"),
        mean_pis=("pis", "mean"),
        enforcement=("enforcement_active", "mean"),
    )
    ax1.bar(hourly_detail.index, hourly_detail["count"], color="#aaaaaa", alpha=0.5, label="Violations")
    ax1.set_ylabel("Violation Count", color="gray")
    ax2 = ax1.twinx()
    ax2.plot(hourly_detail.index, hourly_detail["mean_pis"], color="#ff0000", linewidth=3, label="Mean PIS", marker="o")
    ax2.plot(
        hourly_detail.index,
        hourly_detail["enforcement"] * hourly_detail["mean_pis"].max(),
        color="#00cc00",
        linewidth=2,
        linestyle="--",
        label="Enforcement Activity",
    )
    ax2.set_ylabel("Score")
    ax1.set_xlabel("Hour (IST)")
    ax1.set_title("The Enforcement Gap — High PIS + Zero Enforcement in Evening", fontsize=14, fontweight="bold")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_xticks(range(24))
    fig.tight_layout()
    fig.savefig(output_dir / "07_enforcement_gap.png")
    plt.close(fig)

    # === Chart 10: Vehicle Type × Road Tier Heatmap ===
    logger.info("Chart 10: Vehicle Impact Matrix")
    if "vehicle_type_clean" in df.columns:
        pivot = df.pivot_table(values="pis", index="vehicle_type_clean", columns="road_tier_name", aggfunc="mean")
        # Only keep vehicle types with >100 records and top road tiers
        vtype_counts = df["vehicle_type_clean"].value_counts()
        top_vtypes = vtype_counts[vtype_counts > 100].index
        top_tiers = df["road_tier_name"].value_counts().head(8).index
        pivot = pivot.loc[pivot.index.isin(top_vtypes), pivot.columns.isin(top_tiers)]
        if len(pivot) > 0:
            fig, ax = plt.subplots(figsize=(14, 8))
            sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax, linewidths=0.5)
            ax.set_title("Vehicle Type × Road Tier — Mean PIS", fontsize=14, fontweight="bold")
            ax.set_xlabel("Road Tier")
            ax.set_ylabel("Vehicle Type")
            fig.tight_layout()
            fig.savefig(output_dir / "07_vehicle_road_heatmap.png")
            plt.close(fig)

    # === Chart 11: Cluster Map ===
    logger.info("Chart 11: Cluster Map")
    if len(cluster_stats) > 0:
        fig, ax = plt.subplots(figsize=(14, 12))
        noise = df[df["cluster_id"] == -1]
        ax.scatter(noise["longitude"], noise["latitude"], s=0.5, alpha=0.1, c="gray", label="Unclustered")
        clustered = df[df["cluster_id"] != -1]
        scatter = ax.scatter(
            clustered["longitude"],
            clustered["latitude"],
            c=clustered["pis"],
            cmap="YlOrRd",
            s=2,
            alpha=0.5,
            vmin=0,
            vmax=80,
        )
        # Mark top 20 cluster centroids
        for _, row in cluster_stats.head(20).iterrows():
            ax.annotate(
                f"#{int(row['rank'])}",
                (row["centroid_lon"], row["centroid_lat"]),
                fontsize=8,
                fontweight="bold",
                color="blue",
                ha="center",
                va="center",
                bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.8},
            )
        plt.colorbar(scatter, ax=ax, label="PIS Score", shrink=0.8)
        ax.set_title(f"HDBSCAN Clusters — {len(cluster_stats)} Hotspots Identified", fontsize=14, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        fig.tight_layout()
        fig.savefig(output_dir / "07_cluster_map.png")
        plt.close(fig)

    # === Chart 12: Weight Sensitivity Comparison ===
    logger.info("Chart 12: Weight Sensitivity")
    if weight_results:
        config_names = [k for k in weight_results if not k.startswith("_")]
        means = [weight_results[k]["mean"] for k in config_names]
        stds = [weight_results[k]["std"] for k in config_names]
        fig, ax = plt.subplots(figsize=(12, 6))
        x = range(len(config_names))
        bars = ax.bar(
            x,
            means,
            yerr=stds,
            color=["#ff6600", "#ff0000", "#0088ff", "#00cc66", "#888888"],
            edgecolor="white",
            capsize=5,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(config_names, rotation=30)
        ax.set_ylabel("Mean PIS")
        ax.set_title("Weight Sensitivity — Mean PIS Under Different Schemes", fontsize=14, fontweight="bold")
        for bar, mean in zip(bars, means, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{mean:.1f}", ha="center", fontsize=10)
        fig.tight_layout()
        fig.savefig(output_dir / "07_weight_sensitivity.png")
        plt.close(fig)

    # === Chart 13: Link Road vs Parent Road ===
    logger.info("Chart 13: Link Road Vulnerability")
    link = df[df["is_link_road"] == True]  # noqa: E712
    parent = df[df["is_link_road"] == False]  # noqa: E712
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    axes[0].bar(
        ["Parent Roads", "Link Roads"], [parent["pis"].mean(), link["pis"].mean()], color=["#0088ff", "#ff0000"]
    )
    axes[0].set_title("Mean PIS")
    axes[0].set_ylabel("PIS Score")
    axes[1].bar(
        ["Parent Roads", "Link Roads"],
        [parent["capacity_blocked_pct"].mean(), link["capacity_blocked_pct"].mean()],
        color=["#0088ff", "#ff0000"],
    )
    axes[1].set_title("Mean Capacity Blocked (%)")
    axes[2].bar(["Parent Roads", "Link Roads"], [len(parent) / 1000, len(link) / 1000], color=["#0088ff", "#ff0000"])
    axes[2].set_title("Violation Count (thousands)")
    fig.suptitle("Link Road Vulnerability — Junction Connectors Have Higher Impact", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "07_link_road_vulnerability.png")
    plt.close(fig)

    # === Chart 14: Economic Cost by Road Tier ===
    logger.info("Chart 14: Economic Cost Analysis")
    if "cost_per_hour_inr" in df.columns:
        tier_cost = (
            df.groupby("road_tier_name")["cost_per_hour_inr"].agg(["mean", "sum"]).sort_values("sum", ascending=False)
        )
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        axes[0].barh(tier_cost.index, tier_cost["sum"] / 1e5, color="#00aa44", edgecolor="white")
        axes[0].set_xlabel("Total Cost (₹ lakh/hr)")
        axes[0].set_title("Total Economic Cost by Road Tier")
        axes[0].invert_yaxis()
        axes[1].barh(tier_cost.index, tier_cost["mean"], color="#ff6600", edgecolor="white")
        axes[1].set_xlabel("Mean Cost per Violation (₹/hr)")
        axes[1].set_title("Per-Violation Cost by Road Tier")
        axes[1].invert_yaxis()
        fig.suptitle("Economic Cost of Parking Violations — ₹ per Hour", fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_dir / "07_economic_cost.png")
        plt.close(fig)

    # === Chart 15: PIS Band Summary Dashboard ===
    logger.info("Chart 15: PIS Band Summary")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    band_counts = df["pis_band"].value_counts()
    band_order = ["LOW", "MODERATE", "HIGH", "SEVERE", "CRITICAL"]
    band_colors_list = [PIS_BAND_COLORS.get(b, "#888") for b in band_order]
    vals = [band_counts.get(b, 0) for b in band_order]
    axes[0].bar(band_order, vals, color=band_colors_list, edgecolor="white")
    axes[0].set_title("Violations by PIS Band")
    axes[0].set_ylabel("Count")
    axes[0].tick_params(axis="x", rotation=30)
    # Mean PIS by band
    band_mean = df.groupby("pis_band")["pis"].mean()
    axes[1].bar(band_order, [band_mean.get(b, 0) for b in band_order], color=band_colors_list, edgecolor="white")
    axes[1].set_title("Mean PIS by Band")
    axes[1].set_ylabel("Mean PIS")
    axes[1].tick_params(axis="x", rotation=30)
    # Cost by band
    if "cost_per_hour_inr" in df.columns:
        band_cost = df.groupby("pis_band")["cost_per_hour_inr"].sum()
        axes[2].bar(
            band_order, [band_cost.get(b, 0) / 1e5 for b in band_order], color=band_colors_list, edgecolor="white"
        )
        axes[2].set_title("Total Cost by Band (₹ lakh/hr)")
        axes[2].set_ylabel("₹ lakh/hr")
        axes[2].tick_params(axis="x", rotation=30)
    fig.suptitle("DRISHTAM — PIS Impact Band Summary", fontsize=16, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "07_pis_band_summary.png")
    plt.close(fig)

    logger.info("All %d visualizations saved to %s", 15, output_dir)


# =============================================================================
# RESEARCH REPORT
# =============================================================================


def save_phase2_report(
    df: pd.DataFrame,
    cluster_stats: pd.DataFrame,
    weight_results: dict,
    learned_weights: dict[str, float],
    output_dir: Path,
) -> None:
    """Save Phase 2 research report as markdown."""
    report_path = output_dir / "07_parking_impact_scores.md"

    lines = [
        "# Phase 2 — Parking Impact Score (PIS) Report",
        "",
        "> Auto-generated by `scripts/02_compute_impact_scores.py`",
        "",
        "## PIS Summary",
        "",
        f"- **Records scored**: {len(df):,}",
        f"- **Mean PIS**: {df['pis'].mean():.1f}",
        f"- **Median PIS**: {df['pis'].median():.1f}",
        f"- **Std PIS**: {df['pis'].std():.1f}",
        f"- **Min PIS**: {df['pis'].min():.1f}",
        f"- **Max PIS**: {df['pis'].max():.1f}",
        "",
        "## PIS Band Distribution",
        "",
        "| Band | Count | % |",
        "|---|---|---|",
    ]
    for band in ["LOW", "MODERATE", "HIGH", "SEVERE", "CRITICAL"]:
        count = (df["pis_band"] == band).sum()
        lines.append(f"| {band} | {count:,} | {count / len(df) * 100:.1f}% |")

    if "cost_per_hour_inr" in df.columns:
        total_cost = df["cost_per_hour_inr"].sum()
        daily_cost = total_cost * 8  # 8 peak hours
        annual_cost = daily_cost * 250  # 250 working days
        lines.extend(
            [
                "",
                "## Economic Impact",
                "",
                f"- **Total hourly cost**: ₹{total_cost:,.0f}",
                f"- **Estimated daily cost**: ₹{daily_cost:,.0f} (~₹{daily_cost / 1e7:.1f} crore)",
                f"- **Estimated annual cost**: ₹{annual_cost:,.0f} (~₹{annual_cost / 1e7:.0f} crore)",
            ]
        )

    if "co2_kg_per_hour" in df.columns:
        total_co2 = df["co2_kg_per_hour"].sum()
        annual_co2_tonnes = total_co2 * 8 * 250 / 1000
        trees = annual_co2_tonnes * 1000 / 22
        lines.extend(
            [
                "",
                "## Carbon Impact",
                "",
                f"- **CO₂ per hour (all violations)**: {total_co2:,.0f} kg",
                f"- **Annual estimate**: {annual_co2_tonnes:,.0f} tonnes CO₂",
                f"- **Equivalent trees needed**: {trees:,.0f}",
            ]
        )

    # Learned weights
    lines.extend(
        [
            "",
            "## Data-Driven Weights (Random Forest)",
            "",
            "| Component | Expert Weight | Learned Weight |",
            "|---|---|---|",
        ]
    )
    lines.extend(f"| {comp} | {PIS_WEIGHTS[comp]:.3f} | {learned_weights.get(comp, 0):.3f} |" for comp in PIS_WEIGHTS)

    # Clusters
    if len(cluster_stats) > 0:
        lines.extend(
            [
                "",
                "## Top 10 Enforcement Zones",
                "",
                "| Rank | Violations | Mean PIS | Sum PIS | Location | Top Roads |",
                "|---|---|---|---|---|---|",
            ]
        )
        for _, row in cluster_stats.head(10).iterrows():
            lines.append(
                f"| {int(row['rank'])} | {int(row['violation_count']):,} | {row['mean_pis']:.1f} | "
                f"{row['sum_pis']:,.0f} | ({row['centroid_lat']:.4f}, {row['centroid_lon']:.4f}) | "
                f"{row.get('top_roads', 'N/A')} |"
            )

    # Charts
    lines.extend(
        [
            "",
            "## Visualizations",
            "",
            "![PIS Distribution](07_pis_distribution.png)",
            "![PIS by Road Tier](07_pis_by_road_tier.png)",
            "![PIS Spatial Map](07_pis_spatial_map.png)",
            "![PIS vs Capacity](07_pis_vs_capacity.png)",
            "![Component Breakdown](07_pis_component_breakdown.png)",
            "![Temporal Pattern](07_pis_temporal_pattern.png)",
            "![Top Roads](07_pis_top_roads.png)",
            "![Pareto Analysis](07_pis_pareto.png)",
            "![Enforcement Gap](07_enforcement_gap.png)",
            "![Vehicle Matrix](07_vehicle_road_heatmap.png)",
            "![Cluster Map](07_cluster_map.png)",
            "![Weight Sensitivity](07_weight_sensitivity.png)",
            "![Link Roads](07_link_road_vulnerability.png)",
            "![Economic Cost](07_economic_cost.png)",
            "![Band Summary](07_pis_band_summary.png)",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Research report saved to %s", report_path)


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    """Run the Phase 2 PIS pipeline end-to-end."""
    setup_logging()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 2 — Parking Impact Score Computation")
    logger.info("=" * 70)

    total_start = time.time()
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Load enriched data
    logger.info("--- Step 1: Loading enriched data ---")
    df = pd.read_parquet(ENRICHED_DATA_PATH)
    logger.info("Loaded %d violations × %d features", len(df), len(df.columns))

    # Step 2: Compute PIS
    logger.info("--- Step 2: Computing PIS ---")
    df = compute_pis(df)

    # Step 3: Economic cost + carbon
    logger.info("--- Step 3: Computing economic cost + carbon impact ---")
    df = compute_economic_cost(df)
    df = compute_carbon_impact(df)

    # Step 4: Weight sensitivity
    logger.info("--- Step 4: Weight sensitivity analysis ---")
    weight_results = weight_sensitivity_analysis(df)

    # Step 5: Learn data-driven weights
    logger.info("--- Step 5: Learning data-driven weights ---")
    try:
        events_df = pd.read_csv(EVENT_PATH, low_memory=False)
        events_df = events_df.dropna(subset=["latitude", "longitude"])
        learned_weights = learn_optimal_weights(df, events_df)
    except Exception as e:
        logger.warning("Could not learn weights: %s. Using default.", e)
        learned_weights = dict(PIS_WEIGHTS)

    # Step 6: HDBSCAN clustering
    logger.info("--- Step 6: HDBSCAN clustering ---")
    df = cluster_violations(df)
    cluster_stats = characterize_clusters(df)
    cluster_stats = rank_enforcement_zones(cluster_stats)

    # Step 7: Save updated parquet
    logger.info("--- Step 7: Saving updated parquet ---")
    save_cols = [c for c in df.columns if not c.startswith("_")]
    # Convert list columns if present
    if "violation_types_list" in df.columns:
        df["violation_types_list"] = df["violation_types_list"].apply(
            lambda x: "|".join(x) if isinstance(x, list) else str(x)
        )
    df[save_cols].to_parquet(ENRICHED_DATA_PATH, index=False, engine="pyarrow")
    size_mb = ENRICHED_DATA_PATH.stat().st_size / 1e6
    logger.info("Saved: %s (%.1f MB, %d columns)", ENRICHED_DATA_PATH, size_mb, len(save_cols))

    # Step 8: Generate visualizations
    logger.info("--- Step 8: Generating visualizations ---")
    generate_pis_visualizations(df, cluster_stats, weight_results, RESEARCH_DIR)

    # Step 9: Save report
    logger.info("--- Step 9: Saving research report ---")
    save_phase2_report(df, cluster_stats, weight_results, learned_weights, RESEARCH_DIR)

    # Summary
    total_elapsed = time.time() - total_start
    logger.info("=" * 70)
    logger.info("PHASE 2 COMPLETE in %.1fs", total_elapsed)
    logger.info("PIS: mean=%.1f, median=%.1f (298K violations scored)")
    logger.info("Clusters: %d hotspots identified", len(cluster_stats))
    logger.info("Output: %s", ENRICHED_DATA_PATH)
    logger.info("Charts: %s/07_*.png", RESEARCH_DIR)
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
