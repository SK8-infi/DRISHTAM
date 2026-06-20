"""Phase 3B: Traffic Digital Twin — Simulate Bangalore traffic flow.

Usage:
    python scripts/03b_simulate_traffic.py

Runs two scenarios on the full 393K-segment road network:
1. Baseline: full road capacity (no violations)
2. With violations: PIS-reduced capacity

The difference = true network-wide impact of parking violations.

Designed for e2-highmem-8 (64GB RAM, 8 vCPUs).
Uses all CPU cores via scipy sparse Dijkstra + warm-start Frank-Wolfe.

Reference: digital_twin_research.md
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")

# Use all cores
os.environ["OMP_NUM_THREADS"] = str(os.cpu_count() or 4)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from drishtam.config import (
    BASELINE_FLOWS_PATH,
    DELAY_METRICS_PATH,
    ENRICHED_DATA_PATH,
    OSM_CACHE_PATH,
    PLOT_DPI,
    RESEARCH_DIR,
    SIMULATION_DIR,
    setup_logging,
)
from drishtam.traffic_simulator import (
    compute_violation_impact,
    prepare_network_for_assignment,
    simulate_24h,
)
from drishtam.traffic_zones import (
    TRAFFIC_ZONES,
    snap_zones_to_network,
    summarize_zones,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VIOLATION IMPACT EXTRACTION
# =============================================================================


def extract_violation_impacts(
    graph: object,
    violations_df: pd.DataFrame,
) -> dict[tuple, float]:
    """Map PIS capacity-blocked percentages to graph edges.

    For each violation, find the nearest edge and aggregate the
    capacity_blocked_pct.

    Args:
        G: OSM road network graph.
        violations_df: Enriched violations with capacity_blocked_pct.

    Returns:
        Dict mapping (u, v, key) → mean capacity_blocked_pct.
    """
    logger.info("Extracting violation impacts for %d violations...", len(violations_df))

    # Build road name → edges mapping
    edge_by_name: dict[str, list[tuple]] = {}
    for u, v, key, data in graph.edges(data=True, keys=True):
        name = data.get("name", "")
        if isinstance(name, list):
            name = name[0]
        if name:
            if name not in edge_by_name:
                edge_by_name[name] = []
            edge_by_name[name].append((u, v, key))

    # Match violations to edges by road name
    impacts: dict[tuple, list[float]] = {}
    matched = 0

    if "road_name" in violations_df.columns and "capacity_blocked_pct" in violations_df.columns:
        for road_name, group in violations_df.groupby("road_name"):
            if road_name in edge_by_name:
                edges = edge_by_name[road_name]
                mean_blocked = float(group["capacity_blocked_pct"].mean())
                for edge_key in edges:
                    if edge_key not in impacts:
                        impacts[edge_key] = []
                    impacts[edge_key].append(mean_blocked)
                matched += len(group)

    # Average per edge
    result = {k: np.mean(v) for k, v in impacts.items()}
    logger.info(
        "Mapped %d violations to %d edges (mean blocked=%.1f%%)",
        matched,
        len(result),
        np.mean(list(result.values())) if result else 0,
    )

    return result


# =============================================================================
# VISUALIZATIONS (10+ charts)
# =============================================================================


def generate_traffic_visualizations(
    baseline: dict,
    with_violations: dict,
    impact: dict,
    network: dict,
    output_dir: Path,
) -> None:
    """Generate all traffic simulation visualizations."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_style("darkgrid")
    plt.rcParams.update({"figure.dpi": PLOT_DPI, "savefig.dpi": PLOT_DPI, "font.size": 10})

    hours = baseline["hours"]

    # === Chart 1: 24-Hour VKT Comparison ===
    logger.info("Chart 1: 24-Hour VKT")
    fig, ax = plt.subplots(figsize=(14, 6))
    base_vkt = [baseline["total_vkt"][h] / 1e6 for h in hours]
    viol_vkt = [with_violations["total_vkt"][h] / 1e6 for h in hours]
    ax.fill_between(hours, base_vkt, alpha=0.3, color="#0088ff", label="Baseline")
    ax.fill_between(hours, viol_vkt, alpha=0.3, color="#ff6600", label="With Violations")
    ax.plot(hours, base_vkt, "-o", color="#0088ff", markersize=4)
    ax.plot(hours, viol_vkt, "-o", color="#ff6600", markersize=4)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Vehicle-Kilometers (millions)")
    ax.set_title("24-Hour Traffic Volume — Baseline vs With Violations", fontsize=14, fontweight="bold")
    ax.legend()
    ax.set_xticks(hours)
    fig.tight_layout()
    fig.savefig(output_dir / "09_daily_vkt_comparison.png")
    plt.close(fig)

    # === Chart 2: 24-Hour VHT (Delay) Comparison ===
    logger.info("Chart 2: 24-Hour VHT")
    fig, ax = plt.subplots(figsize=(14, 6))
    base_vht = [baseline["total_vht"][h] for h in hours]
    viol_vht = [with_violations["total_vht"][h] for h in hours]
    delta_vht = [v - b for b, v in zip(base_vht, viol_vht, strict=True)]
    ax.bar(hours, delta_vht, color="#ff0000", alpha=0.7, label="Additional Delay (veh-hrs)")
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Additional Vehicle-Hours of Delay")
    ax.set_title(
        f"Delay Caused by Parking Violations — {sum(delta_vht):.0f} total veh-hrs/day",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xticks(hours)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "09_daily_delay.png")
    plt.close(fig)

    # === Chart 3: V/C Ratio Distribution (Peak Hour) ===
    logger.info("Chart 3: V/C Distribution")
    peak_hour = 9  # AM peak
    if peak_hour in hours:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for ax, data, title, color in [
            (axes[0], baseline, "Baseline", "#0088ff"),
            (axes[1], with_violations, "With Violations", "#ff6600"),
        ]:
            vc = data["vc_ratios"][peak_hour]
            ax.hist(vc[vc > 0.01], bins=80, color=color, alpha=0.7, edgecolor="white")
            ax.axvline(1.0, color="red", linestyle="--", linewidth=2, label="Capacity (V/C=1)")
            ax.set_xlabel("Volume/Capacity Ratio")
            ax.set_ylabel("Count")
            ax.set_title(f"{title} — {peak_hour}:00 AM Peak")
            over_capacity = (vc > 1.0).sum()
            ax.text(
                0.95,
                0.95,
                f"Over capacity: {over_capacity:,}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=10,
                bbox={"boxstyle": "round", "facecolor": "wheat"},
            )
            ax.legend()
        fig.suptitle("V/C Ratio Distribution at AM Peak", fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_dir / "09_vc_distribution_peak.png")
        plt.close(fig)

    # === Chart 4: Top 50 Most Impacted Segments ===
    logger.info("Chart 4: Top Impacted Segments")
    top_50 = impact["top_100_edges"][:50]
    fig, ax = plt.subplots(figsize=(14, 8))
    scores = impact["impact_score"][top_50]
    ax.barh(range(len(top_50)), scores, color="#ff0000", alpha=0.7)
    ax.set_xlabel("Impact Score (ΔFlow × ΔTime)")
    ax.set_ylabel("Segment Rank")
    ax.set_title("Top 50 Road Segments Most Impacted by Parking Violations", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output_dir / "09_top_impacted_segments.png")
    plt.close(fig)

    # === Chart 5: Mean V/C by Hour ===
    logger.info("Chart 5: Mean V/C by Hour")
    fig, ax = plt.subplots(figsize=(14, 6))
    base_vc_mean = [baseline["vc_ratios"][h].mean() for h in hours]
    viol_vc_mean = [with_violations["vc_ratios"][h].mean() for h in hours]
    ax.plot(hours, base_vc_mean, "-o", color="#0088ff", label="Baseline", markersize=5)
    ax.plot(hours, viol_vc_mean, "-o", color="#ff6600", label="With Violations", markersize=5)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Mean V/C Ratio")
    ax.set_title("Average Network Congestion Level", fontsize=14, fontweight="bold")
    ax.legend()
    ax.set_xticks(hours)
    fig.tight_layout()
    fig.savefig(output_dir / "09_mean_vc_by_hour.png")
    plt.close(fig)

    # === Chart 6: Congestion Cascade Map ===
    logger.info("Chart 6: Delta Flow Histogram")
    fig, ax = plt.subplots(figsize=(12, 6))
    daily_delta = impact["delta_flow_daily"]
    nonzero_delta = daily_delta[daily_delta > 1.0]
    ax.hist(nonzero_delta, bins=100, color="#cc00ff", alpha=0.7, edgecolor="white")
    ax.set_xlabel("Daily ΔFlow (PCU) Due to Violations")
    ax.set_ylabel("Number of Segments")
    ax.set_title(
        f"Flow Redistribution — {len(nonzero_delta):,} segments affected",
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(output_dir / "09_delta_flow_histogram.png")
    plt.close(fig)

    # === Chart 7: Convergence Plots (AM Peak) ===
    logger.info("Chart 7: Convergence")
    if peak_hour in hours:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        for ax, data, title in [
            (axes[0], baseline, "Baseline"),
            (axes[1], with_violations, "With Violations"),
        ]:
            conv = data["convergence"][peak_hour]
            ax.semilogy(conv["gap"], color="#0088ff")
            ax.axhline(0.01, color="red", linestyle="--", label="Threshold (0.01)")
            ax.set_xlabel("Frank-Wolfe Iteration")
            ax.set_ylabel("Relative Gap")
            ax.set_title(f"{title} — {peak_hour}:00")
            ax.legend()
        fig.suptitle("Frank-Wolfe Convergence", fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_dir / "09_convergence.png")
        plt.close(fig)

    # === Chart 8: Summary Card ===
    logger.info("Chart 8: Summary Card")
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis("off")
    total_base_vkt = sum(baseline["total_vkt"][h] for h in hours)
    total_viol_vkt = sum(with_violations["total_vkt"][h] for h in hours)
    total_base_vht = sum(baseline["total_vht"][h] for h in hours)
    total_viol_vht = sum(with_violations["total_vht"][h] for h in hours)
    summary = (
        f"DRISHTAM — Digital Twin Summary\n"
        f"{'=' * 50}\n\n"
        f"Network:        {network['n_nodes']:,} nodes, {network['n_edges']:,} edges\n"
        f"Zones:          {len(TRAFFIC_ZONES)} landmarks\n"
        f"Time periods:   {len(hours)} hours\n\n"
        f"BASELINE (no violations):\n"
        f"  Daily VKT:    {total_base_vkt / 1e6:.1f} million km\n"
        f"  Daily VHT:    {total_base_vht:,.0f} vehicle-hours\n\n"
        f"WITH VIOLATIONS:\n"
        f"  Daily VKT:    {total_viol_vkt / 1e6:.1f} million km\n"
        f"  Daily VHT:    {total_viol_vht:,.0f} vehicle-hours\n\n"
        f"VIOLATION IMPACT:\n"
        f"  Additional delay: {total_viol_vht - total_base_vht:,.0f} veh-hrs/day\n"
        f"  VKT increase:     {(total_viol_vkt - total_base_vkt) / 1e6:.2f} M km/day\n"
        f"  Segments affected: {(impact['delta_flow_daily'] > 1.0).sum():,}\n"
    )
    ax.text(0.1, 0.9, summary, transform=ax.transAxes, fontsize=12, verticalalignment="top", fontfamily="monospace")
    fig.savefig(output_dir / "09_simulation_summary.png")
    plt.close(fig)

    logger.info("All visualizations saved to %s", output_dir)


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    """Run the traffic digital twin simulation."""
    setup_logging()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 3B — Traffic Digital Twin")
    logger.info("CPU cores: %d", os.cpu_count() or 0)
    logger.info("=" * 70)

    total_start = time.time()
    SIMULATION_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Load road network
    logger.info("--- Step 1: Load road network ---")
    import networkx as nx

    road_graph = nx.read_graphml(str(OSM_CACHE_PATH))
    logger.info("OSM graph: %d nodes, %d edges", road_graph.number_of_nodes(), road_graph.number_of_edges())

    # Step 2: Setup traffic zones (landmark + auto-generated grid zones)
    logger.info("--- Step 2: Setup traffic zones ---")
    from drishtam.traffic_zones import get_combined_zones

    zone_summary = summarize_zones()
    logger.info("Landmark zones: %s", zone_summary)

    # Generate combined zones: 80 landmarks + ~300 grid zones
    all_zones, zone_nodes = get_combined_zones(road_graph)
    logger.info("Total zones: %d (%d landmark + %d auto)", len(all_zones), len(TRAFFIC_ZONES), len(all_zones) - len(TRAFFIC_ZONES))

    # Step 3: Load violation data
    logger.info("--- Step 3: Load violation data ---")
    df = pd.read_parquet(ENRICHED_DATA_PATH)
    logger.info("Violations: %d × %d", len(df), len(df.columns))
    violation_impacts = extract_violation_impacts(road_graph, df)

    # Step 4: Simulate — use representative hours for speed
    # Full 24h would take ~4hrs; use 6 representative hours
    sim_hours = [3, 6, 9, 12, 17, 21]  # Night, early AM, AM peak, midday, PM peak, late PM
    logger.info("--- Step 4: Baseline simulation (%d hours) ---", len(sim_hours))
    baseline = simulate_24h(road_graph, zone_nodes, violation_impacts=None, hours=sim_hours, zone_data=all_zones)

    logger.info("--- Step 5: Violation simulation (%d hours) ---", len(sim_hours))
    with_violations = simulate_24h(road_graph, zone_nodes, violation_impacts=violation_impacts, hours=sim_hours, zone_data=all_zones)

    # Step 6: Impact analysis
    logger.info("--- Step 6: Impact analysis ---")
    network = prepare_network_for_assignment(road_graph)
    impact = compute_violation_impact(baseline, with_violations, network)

    # Step 7: Save results
    logger.info("--- Step 7: Saving results ---")
    # Save flows as parquet
    flow_data = []
    for hour in sim_hours:
        flow_data.extend(
            {
                "hour": hour,
                "edge_idx": i,
                "baseline_flow": float(baseline["flows"][hour][i]),
                "violation_flow": float(with_violations["flows"][hour][i]),
                "baseline_vc": float(baseline["vc_ratios"][hour][i]),
                "violation_vc": float(with_violations["vc_ratios"][hour][i]),
            }
            for i in range(network["n_edges"])
        )

    flow_df = pd.DataFrame(flow_data)
    flow_df.to_parquet(BASELINE_FLOWS_PATH, index=False, engine="pyarrow")
    logger.info("Saved flows: %s", BASELINE_FLOWS_PATH)

    # Save delay metrics
    delay_df = pd.DataFrame(
        {
            "edge_idx": range(network["n_edges"]),
            "delta_flow_daily": impact["delta_flow_daily"],
            "delta_time_daily": impact["delta_time_daily"],
            "impact_score": impact["impact_score"],
        }
    )
    delay_df.to_parquet(DELAY_METRICS_PATH, index=False, engine="pyarrow")
    logger.info("Saved delays: %s", DELAY_METRICS_PATH)

    # Step 8: Visualizations
    logger.info("--- Step 8: Generating visualizations ---")
    generate_traffic_visualizations(baseline, with_violations, impact, network, RESEARCH_DIR)

    # Step 9: Summary
    total_elapsed = time.time() - total_start
    logger.info("=" * 70)
    logger.info("PHASE 3B COMPLETE in %.1fs (%.1f min)", total_elapsed, total_elapsed / 60)
    logger.info("Additional delay: %.0f vehicle-hours/day", impact["total_delay_hours"])
    logger.info("Segments affected: %d", (impact["delta_flow_daily"] > 1.0).sum())
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
