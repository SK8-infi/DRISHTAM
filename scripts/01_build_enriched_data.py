"""Phase 1: Build enriched violation dataset.

Usage:
    python scripts/01_build_enriched_data.py

This script runs the full data pipeline:
    1. Load raw violation CSV
    2. Load OSM road network
    3. Load ASTraM event data
    4. Spatially enrich violations (nearest road, junction, density)
    5. Add multi-modal features (metro/bus stop proximity)
    6. Run verification checks
    7. Save enriched parquet + generate EDA visualizations

Reference: plans/phase1_data_foundation.md
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

# Force non-interactive backend for saving plots
matplotlib.use("Agg")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from drishtam.config import (
    DATA_DIR,
    ENRICHED_DATA_PATH,
    EVENT_PATH,
    OSM_CACHE_PATH,
    PLOT_DPI,
    RESEARCH_DIR,
    VIOLATION_PATH,
    setup_logging,
)
from drishtam.data_pipeline import (
    enrich_violations,
    load_events,
    load_road_network,
    load_violations,
)
from drishtam.verification import print_enrichment_summary, verify_enriched_data

logger = logging.getLogger(__name__)


def generate_enrichment_visualizations(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Phase 1 EDA visualizations and save to research folder.

    Produces 5+ charts covering feature distributions, spatial patterns,
    and temporal breakdowns of the enriched dataset.

    Args:
        df: Enriched violation DataFrame.
        output_dir: Directory to save PNG files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sns.set_style("darkgrid")
    plt.rcParams.update({"figure.dpi": PLOT_DPI, "savefig.dpi": PLOT_DPI, "font.size": 10})

    # =========================================================================
    # Chart 1: Feature correlation heatmap
    # =========================================================================
    logger.info("Generating Chart 1: Feature correlation heatmap")
    numeric_cols = [
        "capacity_blocked_pct",
        "dist_to_road_m",
        "dist_to_junction_m",
        "violation_density_300m",
        "violation_severity",
        "road_width",
        "road_lanes",
        "temporal_factor",
        "repeat_count",
        "road_importance",
    ]
    available_cols = [c for c in numeric_cols if c in df.columns]
    if len(available_cols) >= 4:
        fig, ax = plt.subplots(figsize=(12, 10))
        corr = df[available_cols].corr()
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(
            corr,
            mask=mask,
            annot=True,
            fmt=".2f",
            cmap="RdBu_r",
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            ax=ax,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8},
        )
        ax.set_title("Feature Correlation Matrix — Enriched Violations", fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_dir / "06_feature_correlation_heatmap.png")
        plt.close(fig)

    # =========================================================================
    # Chart 2: Pairplot of top 6 features
    # =========================================================================
    logger.info("Generating Chart 2: Pairplot of top features")
    pair_cols = [
        "capacity_blocked_pct",
        "road_width",
        "road_lanes",
        "dist_to_junction_m",
        "violation_severity",
        "violation_density_300m",
    ]
    pair_available = [c for c in pair_cols if c in df.columns]
    if len(pair_available) >= 4:
        sample = df[pair_available].sample(min(5000, len(df)), random_state=42)
        g = sns.pairplot(sample, corner=True, plot_kws={"alpha": 0.3, "s": 5})
        g.figure.suptitle("Pairplot — Top Enrichment Features (5K sample)", y=1.02, fontsize=14, fontweight="bold")
        g.savefig(output_dir / "06_feature_pairplot.png")
        plt.close(g.figure)

    # =========================================================================
    # Chart 3: Spatial map colored by capacity blocked
    # =========================================================================
    logger.info("Generating Chart 3: Spatial map by capacity blocked")
    fig, ax = plt.subplots(figsize=(14, 12))
    sample_spatial = df.sample(min(50000, len(df)), random_state=42)
    scatter = ax.scatter(
        sample_spatial["longitude"],
        sample_spatial["latitude"],
        c=sample_spatial["capacity_blocked_pct"],
        cmap="YlOrRd",
        s=1,
        alpha=0.5,
        vmin=0,
        vmax=50,
    )
    plt.colorbar(scatter, ax=ax, label="Capacity Blocked (%)", shrink=0.8)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Bengaluru — Violations by Capacity Blocked", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "06_spatial_capacity_blocked.png")
    plt.close(fig)

    # =========================================================================
    # Chart 4: Temporal patterns by road tier
    # =========================================================================
    logger.info("Generating Chart 4: Temporal patterns by road tier")
    if "hour_ist" in df.columns and "road_tier_name" in df.columns:
        top_tiers = df["road_tier_name"].value_counts().head(5).index.tolist()
        fig, ax = plt.subplots(figsize=(14, 6))
        for tier in top_tiers:
            tier_data = df[df["road_tier_name"] == tier]
            hourly = tier_data.groupby("hour_ist").size()
            ax.plot(hourly.index, hourly.values, label=tier, linewidth=2, marker="o", markersize=3)
        ax.set_xlabel("Hour (IST)")
        ax.set_ylabel("Violation Count")
        ax.set_title("Violation Temporal Profile by Road Tier", fontsize=14, fontweight="bold")
        ax.legend(title="Road Tier")
        ax.set_xticks(range(24))
        ax.axvspan(8, 10, alpha=0.1, color="red", label="Morning peak")
        ax.axvspan(17, 20, alpha=0.1, color="orange", label="Evening peak")
        fig.tight_layout()
        fig.savefig(output_dir / "06_temporal_by_road_tier.png")
        plt.close(fig)

    # =========================================================================
    # Chart 5: Summary dashboard (2x3 grid)
    # =========================================================================
    logger.info("Generating Chart 5: Summary dashboard")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # 5a: Capacity blocked distribution
    if "capacity_blocked_pct" in df.columns:
        axes[0, 0].hist(df["capacity_blocked_pct"], bins=50, color="#ff6600", edgecolor="white", alpha=0.8)
        axes[0, 0].axvline(25, color="red", linestyle="--", label=">25% = High Impact")
        axes[0, 0].set_title("Capacity Blocked Distribution")
        axes[0, 0].set_xlabel("% Blocked")
        axes[0, 0].legend()

    # 5b: Road width distribution
    if "road_width" in df.columns:
        axes[0, 1].hist(df["road_width"], bins=30, color="#0088ff", edgecolor="white", alpha=0.8)
        axes[0, 1].set_title("Road Width Distribution")
        axes[0, 1].set_xlabel("Width (m)")

    # 5c: Distance to road
    if "dist_to_road_m" in df.columns:
        axes[0, 2].hist(df["dist_to_road_m"].clip(upper=200), bins=50, color="#00cc66", edgecolor="white", alpha=0.8)
        axes[0, 2].axvline(
            df["dist_to_road_m"].median(),
            color="red",
            linestyle="--",
            label=f"Median: {df['dist_to_road_m'].median():.0f}m",
        )
        axes[0, 2].set_title("Distance to Nearest Road")
        axes[0, 2].set_xlabel("Distance (m)")
        axes[0, 2].legend()

    # 5d: Violation severity
    if "violation_severity" in df.columns:
        sev_counts = df["violation_severity"].value_counts().sort_index()
        axes[1, 0].bar(sev_counts.index.astype(str), sev_counts.values, color="#cc00ff", alpha=0.8)
        axes[1, 0].set_title("Violation Severity Distribution")
        axes[1, 0].set_xlabel("Severity Score")

    # 5e: Junction distance
    if "dist_to_junction_m" in df.columns:
        axes[1, 1].hist(
            df["dist_to_junction_m"].clip(upper=500), bins=50, color="#ffaa00", edgecolor="white", alpha=0.8
        )
        axes[1, 1].set_title("Distance to Nearest Junction")
        axes[1, 1].set_xlabel("Distance (m)")

    # 5f: Neighborhood density
    if "violation_density_300m" in df.columns:
        axes[1, 2].hist(
            df["violation_density_300m"].clip(upper=500), bins=50, color="#ff0066", edgecolor="white", alpha=0.8
        )
        axes[1, 2].set_title("Neighborhood Density (300m)")
        axes[1, 2].set_xlabel("Count within 300m")

    fig.suptitle("DRISHTAM — Phase 1 Enrichment Summary Dashboard", fontsize=16, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "06_enrichment_summary_dashboard.png")
    plt.close(fig)

    # =========================================================================
    # Chart 6: Multi-modal proximity
    # =========================================================================
    if "dist_to_metro_m" in df.columns and not df["dist_to_metro_m"].isna().all():
        logger.info("Generating Chart 6: Multi-modal proximity")
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        axes[0].hist(df["dist_to_metro_m"].clip(upper=5000), bins=50, color="#00aaff", edgecolor="white", alpha=0.8)
        axes[0].axvline(200, color="red", linestyle="--", label="200m threshold")
        metro_near = df["is_near_metro"].sum()
        axes[0].set_title(f"Distance to Metro ({metro_near:,} within 200m)")
        axes[0].set_xlabel("Distance (m)")
        axes[0].legend()

        if "dist_to_bus_stop_m" in df.columns and not df["dist_to_bus_stop_m"].isna().all():
            axes[1].hist(
                df["dist_to_bus_stop_m"].clip(upper=2000), bins=50, color="#ff6600", edgecolor="white", alpha=0.8
            )
            axes[1].axvline(50, color="red", linestyle="--", label="50m threshold")
            bus_near = df["is_near_bus_stop"].sum()
            axes[1].set_title(f"Distance to Bus Stop ({bus_near:,} within 50m)")
            axes[1].set_xlabel("Distance (m)")
            axes[1].legend()
        else:
            bus_near = df["is_near_bus_stop"].sum()
            axes[1].text(
                0.5,
                0.5,
                f"Bus stop via violation tag\n{bus_near:,} near bus stops",
                transform=axes[1].transAxes,
                ha="center",
                va="center",
                fontsize=14,
            )
            axes[1].set_title("Bus Stop Proximity (tag-based)")

        fig.suptitle("Multi-Modal Transit Proximity", fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_dir / "06_multimodal_proximity.png")
        plt.close(fig)

    logger.info("All visualizations saved to %s", output_dir)


def save_research_report(df: pd.DataFrame, summary: str, output_dir: Path) -> None:
    """Save Phase 1 research report as markdown.

    Args:
        df: Enriched DataFrame.
        summary: Summary text from print_enrichment_summary.
        output_dir: Research directory.
    """
    report_path = output_dir / "06_enriched_data_summary.md"

    lines = [
        "# Phase 1 — Enriched Data Summary",
        "",
        "> Auto-generated by `scripts/01_build_enriched_data.py`",
        "",
        "## Dataset Overview",
        "",
        f"- **Records**: {len(df):,}",
        f"- **Features**: {len(df.columns)}",
        f"- **Memory**: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB",
        "",
        "## Feature Statistics",
        "",
        "```",
        summary,
        "```",
        "",
        "## Column List",
        "",
        "| # | Column | Dtype | Nulls |",
        "|---|---|---|---|",
    ]

    for i, col in enumerate(df.columns, 1):
        dtype = str(df[col].dtype)
        nulls = df[col].isna().sum()
        lines.append(f"| {i} | `{col}` | {dtype} | {nulls:,} |")

    lines.extend(
        [
            "",
            "## Key Distributions",
            "",
            "### Capacity Blocked",
            f"- Mean: {df['capacity_blocked_pct'].mean():.1f}%",
            f"- Median: {df['capacity_blocked_pct'].median():.1f}%",
            f"- >25% (high-impact): {(df['capacity_blocked_pct'] > 25).sum():,}",
            "",
            "### Road Tier Breakdown",
            "",
            "| Tier | Count | % |",
            "|---|---|---|",
        ]
    )

    if "road_tier_name" in df.columns:
        for tier, count in df["road_tier_name"].value_counts().items():
            lines.append(f"| {tier} | {count:,} | {count / len(df) * 100:.1f}% |")

    lines.extend(
        [
            "",
            "## Visualizations",
            "",
            "![Correlation Heatmap](06_feature_correlation_heatmap.png)",
            "![Feature Pairplot](06_feature_pairplot.png)",
            "![Spatial Capacity Map](06_spatial_capacity_blocked.png)",
            "![Temporal by Road Tier](06_temporal_by_road_tier.png)",
            "![Summary Dashboard](06_enrichment_summary_dashboard.png)",
            "![Multi-Modal Proximity](06_multimodal_proximity.png)",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Research report saved to %s", report_path)


def main() -> int:
    """Run the Phase 1 data pipeline end-to-end.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    setup_logging()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 1 — Building Enriched Dataset")
    logger.info("=" * 70)

    total_start = time.time()

    # Ensure output directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Step 1: Load data
    # =========================================================================
    logger.info("--- Step 1: Loading raw data ---")
    viol_df = load_violations(VIOLATION_PATH)
    graph, nodes_gdf, edges_gdf = load_road_network(OSM_CACHE_PATH)
    events_df = load_events(EVENT_PATH)

    logger.info(
        "Loaded: %d violations, %d road edges, %d events",
        len(viol_df),
        len(edges_gdf),
        len(events_df),
    )

    # =========================================================================
    # Step 2: Enrich violations
    # =========================================================================
    logger.info("--- Step 2: Enriching violations ---")
    enriched_df = enrich_violations(viol_df, edges_gdf, nodes_gdf)

    # =========================================================================
    # Step 3: Verification
    # =========================================================================
    logger.info("--- Step 3: Running verification checks ---")
    checks = verify_enriched_data(enriched_df)
    logger.info("Verification: %d/%d checks passed", sum(checks.values()), len(checks))

    # =========================================================================
    # Step 4: Summary
    # =========================================================================
    logger.info("--- Step 4: Generating summary ---")
    summary = print_enrichment_summary(enriched_df)

    # =========================================================================
    # Step 5: Save enriched data
    # =========================================================================
    logger.info("--- Step 5: Saving enriched parquet ---")

    # Select columns to save (drop intermediate columns)
    save_cols = [
        c
        for c in enriched_df.columns
        if c
        not in [
            "violation_type_raw",
            "nearest_edge_idx",
        ]
    ]
    save_df = enriched_df[save_cols].copy()

    # Convert list columns to strings for parquet compatibility
    if "violation_types_list" in save_df.columns:
        save_df["violation_types_list"] = save_df["violation_types_list"].apply(
            lambda x: "|".join(x) if isinstance(x, list) else str(x)
        )

    save_df.to_parquet(ENRICHED_DATA_PATH, index=False, engine="pyarrow")
    file_size_mb = ENRICHED_DATA_PATH.stat().st_size / 1e6
    logger.info("Saved enriched data: %s (%.1f MB)", ENRICHED_DATA_PATH, file_size_mb)

    # =========================================================================
    # Step 6: Generate visualizations
    # =========================================================================
    logger.info("--- Step 6: Generating visualizations ---")
    generate_enrichment_visualizations(enriched_df, RESEARCH_DIR)

    # =========================================================================
    # Step 7: Save research report
    # =========================================================================
    logger.info("--- Step 7: Saving research report ---")
    save_research_report(enriched_df, summary, RESEARCH_DIR)

    # =========================================================================
    # Done
    # =========================================================================
    total_elapsed = time.time() - total_start
    logger.info("=" * 70)
    logger.info("PHASE 1 COMPLETE in %.1fs", total_elapsed)
    logger.info("Output: %s", ENRICHED_DATA_PATH)
    logger.info("Charts: %s/06_*.png", RESEARCH_DIR)
    logger.info("Report: %s/06_enriched_data_summary.md", RESEARCH_DIR)
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
