"""DRISHTAM Parking Impact Score (PIS) engine.

Computes a 0-100 impact score for each parking violation based on six
weighted components: capacity blocked, road importance, junction proximity,
temporal context, neighborhood density, and violation severity.

Also computes economic cost (₹/hour) and carbon impact (kg CO₂/hour)
per violation as novel enhancement layers.

Reference: plans/phase2_impact_scoring.md
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from drishtam.config import (
    CO2_PER_IDLE_HOUR_KG,
    COST_PER_VEHICLE_HOUR_INR,
    DELAY_FACTOR_PER_PIS,
    JUNCTION_PROXIMITY_DECAY_M,
    PIS_BANDS,
    PIS_MAX_SCORE,
    PIS_WEIGHTS,
    TRAFFIC_FLOW_ESTIMATES,
    WEIGHT_CONFIGS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. PIS COMPONENT FUNCTIONS (each returns 0-1 normalized score)
# =============================================================================


def compute_capacity_factor(df: pd.DataFrame) -> np.ndarray:
    """Compute capacity factor: fraction of road blocked by the vehicle.

    This is the most important PIS component (w=0.30). A car (2.0m) on a
    6m residential road blocks 33%, while a scooter on a primary road
    blocks only 5%.

    Args:
        df: DataFrame with 'vehicle_width_m' and 'road_width' columns.

    Returns:
        Array of scores in [0, 1].
    """
    return np.clip(df["vehicle_width_m"].values / df["road_width"].values, 0, 1)


def compute_road_importance(df: pd.DataFrame) -> np.ndarray:
    """Compute road importance: how critical is this road to the network?

    Combines the road hierarchy importance score with a lane factor
    (more lanes = more traffic served) and a link road bonus (junction
    connectors are critical bottleneck points).

    Args:
        df: DataFrame with 'road_importance', 'road_lanes', 'is_link_road'.

    Returns:
        Array of scores in [0, 1].
    """
    importance = df["road_importance"].values.astype(float)
    lane_factor = np.clip(df["road_lanes"].values / 4.0, 0.25, 1.0)
    link_bonus = np.where(df["is_link_road"].values, 1.3, 1.0)

    raw = importance * lane_factor * link_bonus
    # Normalize to [0, 1]
    max_val = raw.max()
    if max_val > 0:
        return np.clip(raw / max_val, 0, 1)
    return raw


def compute_junction_factor(df: pd.DataFrame) -> np.ndarray:
    """Compute junction proximity factor: exponential decay from intersections.

    Violations near junctions cause cascading delays because they affect
    multiple traffic streams. Score decays exponentially with distance.

    At junction (0m): 1.0, at 50m: 0.61, at 100m: 0.37, at 500m: ~0.

    Bonus: scaled by junction_degree / max_degree for major intersections.

    Args:
        df: DataFrame with 'dist_to_junction_m' and 'junction_degree'.

    Returns:
        Array of scores in [0, 1].
    """
    dist = df["dist_to_junction_m"].values
    degree = df["junction_degree"].values.astype(float)

    # Exponential decay with distance
    distance_score = np.exp(-dist / JUNCTION_PROXIMITY_DECAY_M)

    # Degree normalization (higher degree = more critical junction)
    max_degree = max(degree.max(), 1)
    degree_score = degree / max_degree

    # Combined: geometric mean gives balanced weighting
    raw = np.sqrt(distance_score * degree_score)
    return np.clip(raw, 0, 1)


def compute_temporal_factor(df: pd.DataFrame) -> np.ndarray:
    """Compute temporal factor: is this during peak traffic hours?

    Uses the pre-computed temporal_factor from Phase 1 which already
    accounts for IST hour mapping and weekend multiplier.

    Args:
        df: DataFrame with 'temporal_factor' column.

    Returns:
        Array of scores in [0, 1].
    """
    return np.clip(df["temporal_factor"].values, 0, 1)


def compute_density_factor(df: pd.DataFrame) -> np.ndarray:
    """Compute density factor: how clustered are violations nearby?

    Multiple violations in the same area compound each other's impact.
    Uses log-normalized density to handle the heavy-tailed distribution.

    Args:
        df: DataFrame with 'violation_density_300m' column.

    Returns:
        Array of scores in [0, 1].
    """
    density = df["violation_density_300m"].values.astype(float)
    log_density = np.log1p(density)
    max_log = log_density.max()
    if max_log > 0:
        return log_density / max_log
    return np.zeros(len(df))


def compute_severity_factor(df: pd.DataFrame) -> np.ndarray:
    """Compute violation severity factor.

    Uses the pre-computed violation_severity from Phase 1 which maps
    violation types to 0-1 severity scores (DOUBLE_PARKING=1.0, etc.).

    Args:
        df: DataFrame with 'violation_severity' column.

    Returns:
        Array of scores in [0, 1].
    """
    return np.clip(df["violation_severity"].values, 0, 1)


# =============================================================================
# 2. MASTER PIS COMPUTATION
# =============================================================================

# Map component names to their compute functions
COMPONENT_FUNCTIONS = {
    "capacity": compute_capacity_factor,
    "importance": compute_road_importance,
    "junction": compute_junction_factor,
    "temporal": compute_temporal_factor,
    "density": compute_density_factor,
    "severity": compute_severity_factor,
}


def compute_pis(
    df: pd.DataFrame,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute Parking Impact Score (0-100) for each violation.

    Combines six weighted components into a composite score, assigns
    PIS bands, and adds economic cost + carbon impact estimates.

    Args:
        df: Enriched violation DataFrame from Phase 1.
        weights: Optional weight overrides. Must sum to ~1.0.
            Defaults to PIS_WEIGHTS from config.

    Returns:
        DataFrame with added columns: pis, pis_band, pis_color,
        and all six component score columns (pis_capacity, etc.).
    """
    if weights is None:
        weights = PIS_WEIGHTS

    # Validate weights sum to ~1.0
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        logger.warning("PIS weights sum to %.3f, expected 1.0. Normalizing.", weight_sum)
        weights = {k: v / weight_sum for k, v in weights.items()}

    logger.info("Computing PIS with weights: %s", {k: f"{v:.3f}" for k, v in weights.items()})

    df = df.copy()

    # Compute each component
    components = {}
    for name, func in COMPONENT_FUNCTIONS.items():
        score = func(df)
        components[name] = score
        df[f"pis_{name}"] = score
        logger.info(
            "  %s: mean=%.3f, min=%.3f, max=%.3f",
            name,
            score.mean(),
            score.min(),
            score.max(),
        )

    # Weighted sum → scale to 0-100
    pis_raw = sum(weights[name] * components[name] for name in weights)
    df["pis"] = np.clip(pis_raw * PIS_MAX_SCORE, 0, PIS_MAX_SCORE)

    # PIS band classification
    df["pis_band"] = _classify_pis_band(df["pis"].values)

    logger.info(
        "PIS computed: mean=%.1f, median=%.1f, std=%.1f, min=%.1f, max=%.1f",
        df["pis"].mean(),
        df["pis"].median(),
        df["pis"].std(),
        df["pis"].min(),
        df["pis"].max(),
    )

    # Band distribution
    band_counts = df["pis_band"].value_counts()
    for band, count in band_counts.items():
        logger.info("  %s: %d (%.1f%%)", band, count, count / len(df) * 100)

    return df


def compute_all_component_scores(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Compute all six PIS component scores without combining them.

    Useful for weight sensitivity analysis where we need raw components
    to re-weight without recomputation.

    Args:
        df: Enriched violation DataFrame.

    Returns:
        Dict mapping component name to score array.
    """
    return {name: func(df) for name, func in COMPONENT_FUNCTIONS.items()}


# =============================================================================
# 3. ECONOMIC COST & CARBON IMPACT (Novel Enhancement Layers A & B)
# =============================================================================


def compute_economic_cost(df: pd.DataFrame) -> pd.DataFrame:
    """Compute economic cost (₹/hour) per violation.

    Estimates the hourly congestion cost caused by each violation
    based on PIS score, road traffic volume, and delay factor.

    Formula: cost = vehicles_per_hour × delay_fraction × cost_per_vehicle_hour
    where delay_fraction = PIS / 100 × DELAY_FACTOR_PER_PIS × 100

    Args:
        df: DataFrame with 'pis', 'road_tier_name', 'peak_period'.

    Returns:
        DataFrame with 'cost_per_hour_inr' and 'affected_vehicles_per_hour'.
    """
    df = df.copy()

    # Map road tier to traffic volume
    is_peak = df["peak_period"].isin(["morning_peak", "evening_peak"])
    traffic_key = np.where(is_peak, "peak", "offpeak")

    vehicles_per_hour = np.array(
        [
            TRAFFIC_FLOW_ESTIMATES.get(tier, {"peak": 100, "offpeak": 40})[key]
            for tier, key in zip(df["road_tier_name"].values, traffic_key, strict=True)
        ],
        dtype=float,
    )

    df["affected_vehicles_per_hour"] = vehicles_per_hour

    # Delay fraction: PIS × 0.3% per point
    delay_fraction = df["pis"].values / PIS_MAX_SCORE * DELAY_FACTOR_PER_PIS * PIS_MAX_SCORE

    # Cost = vehicles × delay × cost_per_vehicle_hour
    df["cost_per_hour_inr"] = vehicles_per_hour * delay_fraction * COST_PER_VEHICLE_HOUR_INR

    logger.info(
        "Economic cost: mean=₹%.0f/hr, max=₹%.0f/hr, total daily estimate=₹%.0f lakh",
        df["cost_per_hour_inr"].mean(),
        df["cost_per_hour_inr"].max(),
        df["cost_per_hour_inr"].sum() / 1e5,
    )

    return df


def compute_carbon_impact(df: pd.DataFrame) -> pd.DataFrame:
    """Compute carbon impact (kg CO₂/hour) per violation.

    Estimates CO₂ emissions from vehicles idling due to parking-induced
    congestion. Each PIS point implies a small effective delay.

    Args:
        df: DataFrame with 'pis', 'affected_vehicles_per_hour'.

    Returns:
        DataFrame with 'co2_kg_per_hour' column.
    """
    df = df.copy()

    if "affected_vehicles_per_hour" not in df.columns:
        df = compute_economic_cost(df)

    # Induced idle time per vehicle (hours)
    delay_fraction = df["pis"].values / PIS_MAX_SCORE * DELAY_FACTOR_PER_PIS * PIS_MAX_SCORE

    # CO2 = vehicles × delay_fraction × co2_per_idle_hour
    df["co2_kg_per_hour"] = df["affected_vehicles_per_hour"].values * delay_fraction * CO2_PER_IDLE_HOUR_KG

    total_annual_tonnes = df["co2_kg_per_hour"].sum() * 8 * 250 / 1000  # 8 peak hours × 250 days
    logger.info(
        "Carbon impact: mean=%.2f kg/hr, total annual estimate=%.0f tonnes CO₂",
        df["co2_kg_per_hour"].mean(),
        total_annual_tonnes,
    )

    return df


# =============================================================================
# 4. WEIGHT SENSITIVITY ANALYSIS
# =============================================================================


def weight_sensitivity_analysis(
    df: pd.DataFrame,
) -> dict[str, dict]:
    """Compare PIS under different weight configurations.

    Tests 5 weight schemes and computes rank correlations, distribution
    stats, and top-20 road overlap to assess sensitivity.

    Args:
        df: Enriched violation DataFrame.

    Returns:
        Dict with results per weight config: {config_name: {pis, stats, top_roads}}.
    """
    from scipy.stats import spearmanr

    logger.info("Running weight sensitivity analysis with %d configurations", len(WEIGHT_CONFIGS))

    # Pre-compute all component scores once
    components = compute_all_component_scores(df)

    results = {}
    pis_arrays = {}

    for config_name, weights in WEIGHT_CONFIGS.items():
        # Compute PIS with these weights
        pis_raw = sum(weights[name] * components[name] for name in weights)
        pis = np.clip(pis_raw * PIS_MAX_SCORE, 0, PIS_MAX_SCORE)
        pis_arrays[config_name] = pis

        # Top 20 roads by mean PIS
        df_temp = df.copy()
        df_temp["_pis"] = pis
        top_roads = (
            df_temp.groupby("road_name")["_pis"]
            .agg(["mean", "count"])
            .query("count >= 20")
            .sort_values("mean", ascending=False)
            .head(20)
            .index.tolist()
        )

        results[config_name] = {
            "weights": weights,
            "mean": float(pis.mean()),
            "median": float(np.median(pis)),
            "std": float(pis.std()),
            "top_20_roads": top_roads,
        }

        logger.info(
            "  %s: mean=%.1f, median=%.1f, std=%.1f",
            config_name,
            results[config_name]["mean"],
            results[config_name]["median"],
            results[config_name]["std"],
        )

    # Rank correlations between all pairs
    config_names = list(pis_arrays.keys())
    rank_corr = {}
    for i, name_a in enumerate(config_names):
        for name_b in config_names[i + 1 :]:
            rho, _ = spearmanr(pis_arrays[name_a], pis_arrays[name_b])
            rank_corr[f"{name_a}_vs_{name_b}"] = float(rho)

    results["_rank_correlations"] = rank_corr
    logger.info("Rank correlations: %s", {k: f"{v:.3f}" for k, v in rank_corr.items()})

    return results


def learn_optimal_weights(
    df: pd.DataFrame,
    events_df: pd.DataFrame,
    grid_size_m: int = 500,
) -> dict[str, float]:
    """Learn data-driven PIS weights using Random Forest.

    Uses event density in grid cells as a proxy for ground truth.
    Trains RF: features = [6 PIS components], target = event_density.
    Extracts feature importances as data-driven weights.

    Args:
        df: Enriched violation DataFrame.
        events_df: Event DataFrame with lat/lon.
        grid_size_m: Grid cell size in meters for spatial binning.

    Returns:
        Dict of learned weights (normalized to sum=1).
    """
    from sklearn.ensemble import RandomForestRegressor

    logger.info("Learning optimal weights via Random Forest (grid_size=%dm)", grid_size_m)

    # Pre-compute components
    components = compute_all_component_scores(df)
    component_names = list(components.keys())

    # Create grid cells
    lat_step = grid_size_m / 111000
    lon_step = grid_size_m / 108000

    df_temp = df.copy()
    df_temp["grid_lat"] = (df_temp["latitude"] / lat_step).astype(int)
    df_temp["grid_lon"] = (df_temp["longitude"] / lon_step).astype(int)
    df_temp["grid_id"] = df_temp["grid_lat"].astype(str) + "_" + df_temp["grid_lon"].astype(str)

    # Add component scores
    for name in component_names:
        df_temp[f"comp_{name}"] = components[name]

    # Aggregate by grid cell
    grid_features = df_temp.groupby("grid_id").agg(
        **{f"mean_{name}": (f"comp_{name}", "mean") for name in component_names},
        violation_count=("pis_capacity" if "pis_capacity" in df_temp.columns else "latitude", "count"),
    )

    # Event density per grid cell
    events_temp = events_df.copy()
    events_temp["grid_lat"] = (events_temp["latitude"] / lat_step).astype(int)
    events_temp["grid_lon"] = (events_temp["longitude"] / lon_step).astype(int)
    events_temp["grid_id"] = events_temp["grid_lat"].astype(str) + "_" + events_temp["grid_lon"].astype(str)

    event_counts = events_temp.groupby("grid_id").size().rename("event_density")

    # Merge
    grid_data = grid_features.join(event_counts, how="inner")
    grid_data = grid_data.dropna()

    if len(grid_data) < 50:
        logger.warning(
            "Too few grid cells with both violations and events (%d). Using default weights.", len(grid_data)
        )
        return dict(PIS_WEIGHTS)

    # Train Random Forest
    feature_cols = [f"mean_{name}" for name in component_names]
    x_train = grid_data[feature_cols].values
    y = grid_data["event_density"].values

    rf = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
    rf.fit(x_train, y)

    r2 = rf.score(x_train, y)
    importances = rf.feature_importances_

    # Normalize to weights
    learned_weights = {name: float(imp) for name, imp in zip(component_names, importances, strict=True)}
    total = sum(learned_weights.values())
    learned_weights = {k: v / total for k, v in learned_weights.items()}

    logger.info("Learned weights (R²=%.3f): %s", r2, {k: f"{v:.3f}" for k, v in learned_weights.items()})

    return learned_weights


# =============================================================================
# 5. HELPERS
# =============================================================================


def _classify_pis_band(pis_values: np.ndarray) -> list[str]:
    """Classify PIS values into impact bands.

    Args:
        pis_values: Array of PIS scores (0-100).

    Returns:
        List of band names (LOW, MODERATE, HIGH, SEVERE, CRITICAL).
    """
    bands = []
    for pis in pis_values:
        band = "LOW"
        for low, high, name in PIS_BANDS:
            if low <= pis < high:
                band = name
                break
        if pis >= 80:
            band = "CRITICAL"
        bands.append(band)
    return bands
