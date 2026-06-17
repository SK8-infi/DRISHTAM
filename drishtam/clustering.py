"""DRISHTAM hotspot clustering via HDBSCAN.

Identifies spatial clusters of parking violations and characterizes
each cluster by impact metrics, road composition, and temporal patterns.
Used for enforcement zone prioritization.

Reference: plans/phase2_impact_scoring.md §2.3
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from drishtam.config import (
    HDBSCAN_MIN_CLUSTER_SIZE,
    HDBSCAN_MIN_SAMPLES,
    LAT_TO_METERS,
    LON_TO_METERS,
)

logger = logging.getLogger(__name__)


def cluster_violations(df: pd.DataFrame) -> pd.DataFrame:
    """Run HDBSCAN spatial clustering on violation locations.

    Groups violations into geographic clusters based on proximity.
    Points not assigned to any cluster get cluster_id = -1 (noise).

    Args:
        df: DataFrame with 'latitude', 'longitude', and 'pis' columns.

    Returns:
        DataFrame with added 'cluster_id' column.
    """
    import hdbscan

    logger.info(
        "Running HDBSCAN clustering (min_cluster_size=%d, min_samples=%d)",
        HDBSCAN_MIN_CLUSTER_SIZE,
        HDBSCAN_MIN_SAMPLES,
    )

    # Convert to meters for meaningful distance thresholds
    coords = np.column_stack(
        [
            df["latitude"].values * LAT_TO_METERS,
            df["longitude"].values * LON_TO_METERS,
        ]
    )

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=HDBSCAN_MIN_CLUSTER_SIZE,
        min_samples=HDBSCAN_MIN_SAMPLES,
        metric="euclidean",
        cluster_selection_method="eom",
        core_dist_n_jobs=-1,
    )
    labels = clusterer.fit_predict(coords)

    df = df.copy()
    df["cluster_id"] = labels

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    noise_pct = n_noise / len(df) * 100

    logger.info(
        "Clustering complete: %d clusters, %d noise points (%.1f%%)",
        n_clusters,
        n_noise,
        noise_pct,
    )

    return df


def characterize_clusters(df: pd.DataFrame) -> pd.DataFrame:
    """Compute summary statistics for each cluster.

    Produces a DataFrame with one row per cluster containing location,
    size, impact metrics, road composition, and temporal patterns.

    Args:
        df: DataFrame with 'cluster_id', 'pis', and enrichment columns.

    Returns:
        DataFrame with cluster characteristics, sorted by aggregate_impact.
    """
    import pandas as _pd  # noqa: F811

    logger.info("Characterizing clusters...")

    # Filter out noise
    clustered = df[df["cluster_id"] != -1].copy()

    if len(clustered) == 0:
        logger.warning("No clusters found — all points are noise.")
        return _pd.DataFrame()

    agg = clustered.groupby("cluster_id").agg(
        violation_count=("pis", "count"),
        mean_pis=("pis", "mean"),
        max_pis=("pis", "max"),
        sum_pis=("pis", "sum"),
        centroid_lat=("latitude", "mean"),
        centroid_lon=("longitude", "mean"),
        mean_capacity_blocked=("capacity_blocked_pct", "mean"),
        mean_road_width=("road_width", "mean"),
        mean_road_lanes=("road_lanes", "mean"),
    )

    # Dominant road type per cluster
    road_mode = clustered.groupby("cluster_id")["road_tier_name"].agg(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "Unknown"
    )
    agg["dominant_road_type"] = road_mode

    # Dominant violation type per cluster
    if "primary_violation" in clustered.columns:
        viol_mode = clustered.groupby("cluster_id")["primary_violation"].agg(
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "Unknown"
        )
        agg["dominant_violation"] = viol_mode

    # Peak hour per cluster
    if "hour_ist" in clustered.columns:
        peak_hour = clustered.groupby("cluster_id")["hour_ist"].agg(
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 0
        )
        agg["peak_hour"] = peak_hour

    # Top road names in cluster
    def _top_roads(group: pd.DataFrame) -> str:
        roads = group["road_name"].value_counts().head(3)
        return " | ".join(f"{name} ({cnt})" for name, cnt in roads.items())

    top_roads = clustered.groupby("cluster_id").apply(_top_roads, include_groups=False)
    agg["top_roads"] = top_roads

    # Economic cost if available
    if "cost_per_hour_inr" in clustered.columns:
        cost_agg = clustered.groupby("cluster_id")["cost_per_hour_inr"].sum()
        agg["total_cost_per_hour_inr"] = cost_agg

    # Sort by aggregate impact (sum of PIS)
    agg = agg.sort_values("sum_pis", ascending=False)
    agg["rank"] = range(1, len(agg) + 1)

    logger.info("Top 5 clusters by aggregate impact:")
    for _, row in agg.head(5).iterrows():
        logger.info(
            "  Rank %d: %d violations, mean PIS=%.1f, sum PIS=%.0f, at (%.4f, %.4f)",
            row["rank"],
            row["violation_count"],
            row["mean_pis"],
            row["sum_pis"],
            row["centroid_lat"],
            row["centroid_lon"],
        )

    return agg.reset_index()


def rank_enforcement_zones(
    cluster_stats: pd.DataFrame,
    top_n: int = 20,
) -> pd.DataFrame:
    """Select top-N enforcement priority zones.

    Ranks clusters by aggregate impact (sum of PIS in cluster) and
    returns the top zones with actionable enforcement recommendations.

    Args:
        cluster_stats: Output of characterize_clusters().
        top_n: Number of top zones to return.

    Returns:
        Top-N clusters with enforcement priority ranking.
    """
    if len(cluster_stats) == 0:
        return cluster_stats

    top = cluster_stats.head(top_n).copy()
    top["priority"] = ["CRITICAL" if r <= 5 else "HIGH" if r <= 10 else "MODERATE" for r in top["rank"]]

    logger.info("Top %d enforcement zones identified", len(top))
    return top
