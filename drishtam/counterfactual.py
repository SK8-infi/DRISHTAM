"""DRISHTAM Engine 2 — Counterfactual What-If Simulator.

Uses the trained GBM model to simulate enforcement scenarios.
Instead of re-running the 8-hour traffic simulation, we modify
input features (zero out violations) and re-predict impact scores.

Usage:
    from drishtam.counterfactual import WhatIfEngine
    engine = WhatIfEngine()
    result = engine.run_scenario("Remove BSF STS Road", road_names=["BSF STS Road"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
import pandas as pd

from drishtam.config import (
    ENRICHED_DATA_PATH,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "models"

# Violation-related feature indices in the 36D feature vector
# See notebooks/03c_gnn_final.py § 7 for full mapping
VIOL_FEATURE_INDICES = {
    "viol_cnt": 9,      # log1p(violation count)
    "pis": 10,          # max PIS
    "has_v": 11,        # has violations binary
    "cap_blk": 12,      # capacity blocked %
    "peak_v": 13,       # log1p(peak hour violations)
    "viol_dens": 14,    # violations per 100m
    "severity": 15,     # mean severity
}

# 1-hop neighborhood violation features
NBR1_FEATURE_INDICES = {
    "nbr1_v": 16,       # log1p(neighbor violation sum)
    "nbr1_pis": 17,     # neighbor max PIS
    "nbr1_cap": 18,     # neighbor max capacity blocked
    "nbr1_avg": 19,     # neighbor avg violations
}

# 2-hop neighborhood violation features
NBR2_FEATURE_INDICES = {
    "nbr2_v": 21,       # log1p(2-hop neighbor violations)
    "nbr2_pis": 22,     # 2-hop max PIS
}

# Interaction features involving violations
INTERACTION_INDICES = {
    "t×v": 24,          # tier × violations
    "l×c": 25,          # lanes × cap_blocked
    "t×nv": 26,         # tier × nbr_viol
    "v×nv": 27,         # local × nbr violations
    "bc×v": 28,         # betweenness × violations
    "cap×cb": 30,       # capacity × cap_blocked
    "dens×t": 31,       # density × tier
    "bc×nv": 32,        # betweenness × nbr_viol
    "cap×v": 34,        # capacity × violations
    "bc×cb": 35,        # betweenness × cap_blocked
}

ALL_VIOL_INDICES = (
    list(VIOL_FEATURE_INDICES.values())
    + list(NBR1_FEATURE_INDICES.values())
    + list(NBR2_FEATURE_INDICES.values())
    + list(INTERACTION_INDICES.values())
)


@dataclass
class ScenarioResult:
    """Result of a counterfactual scenario."""
    name: str
    description: str
    violations_removed: int
    total_violations: int
    pct_violations_removed: float
    baseline_impact: float
    scenario_impact: float
    impact_reduction: float
    pct_reduction: float
    segments_improved: int
    top_improved_segments: list[dict] = field(default_factory=list)
    cost_benefit: float = 0.0  # reduction per violation removed


class WhatIfEngine:
    """Counterfactual What-If simulator using trained GBM."""

    def __init__(self) -> None:
        logger.info("Loading What-If Engine...")

        # Load GBM model
        gbm_path = MODELS_DIR / "gbm_36d_best.pkl"
        self.gbm = joblib.load(gbm_path)
        logger.info(f"  GBM loaded from {gbm_path}")

        # Load features
        self.features = np.load(MODELS_DIR / "features_36d.npy")
        self.scaler = joblib.load(MODELS_DIR / "feature_scaler.pkl")
        logger.info(f"  Features: {self.features.shape}")

        # Load segment predictions (for metadata)
        self.segments = pd.read_parquet(MODELS_DIR / "segment_predictions.parquet")
        logger.info(f"  Segments: {self.segments.shape}")

        # Load violations
        self.violations = pd.read_parquet(ENRICHED_DATA_PATH)
        self.total_violations = len(self.violations)
        logger.info(f"  Violations: {self.total_violations}")

        # Compute baseline
        self._compute_baseline()

    def _compute_baseline(self) -> None:
        """Compute baseline impact with all violations active."""
        features_scaled = self.scaler.transform(self.features)
        self.baseline_preds = self.gbm.predict(features_scaled)
        self.baseline_impact = float(self.baseline_preds.sum())
        self.baseline_affected = int((self.baseline_preds > 0.01).sum())
        self.baseline_critical = int((self.baseline_preds > 0.5).sum())
        logger.info(
            f"  Baseline: total_impact={self.baseline_impact:.1f}, "
            f"affected={self.baseline_affected}, critical={self.baseline_critical}"
        )

    def _get_segment_indices_for_roads(self, road_names: list[str]) -> np.ndarray:
        """Find segment indices matching given road names."""
        mask = self.segments["road_name"].isin(road_names)
        return np.where(mask.values)[0]

    def _get_violation_mask(self, **criteria: Any) -> np.ndarray:
        """Create boolean mask for violations matching criteria.

        Supported criteria:
            road_names: list of road names
            pis_min: minimum PIS threshold
            capacity_blocked_min: minimum capacity_blocked_pct
            vehicle_types: list of vehicle types
            cluster_ids: list of cluster IDs
            hour_range: tuple (start, end) for hour_ist
            is_link_road: bool
            repeat_count_min: minimum repeat_count
        """
        mask = np.ones(len(self.violations), dtype=bool)

        if "road_names" in criteria:
            mask &= self.violations["road_name"].isin(criteria["road_names"]).values
        if "pis_min" in criteria:
            mask &= (self.violations["pis"] >= criteria["pis_min"]).values
        if "capacity_blocked_min" in criteria:
            mask &= (self.violations["capacity_blocked_pct"] >= criteria["capacity_blocked_min"]).values
        if "vehicle_types" in criteria:
            mask &= self.violations["vehicle_type_clean"].isin(criteria["vehicle_types"]).values
        if "cluster_ids" in criteria:
            mask &= self.violations["cluster_id"].isin(criteria["cluster_ids"]).values
        if "hour_range" in criteria:
            h_start, h_end = criteria["hour_range"]
            mask &= ((self.violations["hour_ist"] >= h_start) & (self.violations["hour_ist"] <= h_end)).values
        if "is_link_road" in criteria:
            mask &= (self.violations["is_link_road"] == criteria["is_link_road"]).values
        if "repeat_count_min" in criteria:
            mask &= (self.violations["repeat_count"] >= criteria["repeat_count_min"]).values

        return mask

    def simulate_intervention(
        self,
        violation_mask: np.ndarray,
        segment_indices: np.ndarray | None = None,
    ) -> tuple[np.ndarray, float]:
        """Simulate removing violations by zeroing their features.

        Args:
            violation_mask: boolean mask of violations to REMOVE
            segment_indices: optional pre-computed segment indices to modify

        Returns:
            (new_predictions, new_total_impact)
        """
        # If no specific segments given, find affected segments from violations
        if segment_indices is None:
            affected_roads = self.violations.loc[violation_mask, "road_name"].unique()
            segment_indices = self._get_segment_indices_for_roads(list(affected_roads))

        if len(segment_indices) == 0:
            return self.baseline_preds.copy(), self.baseline_impact

        # Copy features and zero out violation-related features
        new_features = self.features.copy()
        for idx in ALL_VIOL_INDICES:
            new_features[segment_indices, idx] = 0.0

        # Re-predict
        new_scaled = self.scaler.transform(new_features)
        new_preds = self.gbm.predict(new_scaled)

        return new_preds, float(new_preds.sum())

    def run_scenario(
        self,
        name: str,
        description: str = "",
        **criteria: Any,
    ) -> ScenarioResult:
        """Run a complete counterfactual scenario."""
        violation_mask = self._get_violation_mask(**criteria)
        n_removed = int(violation_mask.sum())

        if n_removed == 0:
            return ScenarioResult(
                name=name, description=description,
                violations_removed=0, total_violations=self.total_violations,
                pct_violations_removed=0.0,
                baseline_impact=self.baseline_impact,
                scenario_impact=self.baseline_impact,
                impact_reduction=0.0, pct_reduction=0.0,
                segments_improved=0,
            )

        # Get segment indices for affected roads
        segment_indices = None
        if "road_names" in criteria:
            segment_indices = self._get_segment_indices_for_roads(criteria["road_names"])

        new_preds, new_impact = self.simulate_intervention(violation_mask, segment_indices)

        # Compute deltas
        delta = self.baseline_preds - new_preds
        improved = delta > 0.001
        reduction = self.baseline_impact - new_impact
        pct_reduction = (reduction / self.baseline_impact * 100) if self.baseline_impact > 0 else 0

        # Top improved segments
        top_idx = np.argsort(delta)[::-1][:20]
        top_improved = []
        for idx in top_idx:
            if delta[idx] <= 0.001:
                break
            row = self.segments.iloc[idx]
            top_improved.append({
                "seg_idx": int(idx),
                "road_name": str(row.get("road_name", "")),
                "highway": str(row.get("highway", "")),
                "lat": float(row.get("lat", 0)),
                "lon": float(row.get("lon", 0)),
                "baseline_impact": float(self.baseline_preds[idx]),
                "new_impact": float(new_preds[idx]),
                "improvement": float(delta[idx]),
            })

        cost_benefit = pct_reduction / max(n_removed, 1)

        result = ScenarioResult(
            name=name,
            description=description,
            violations_removed=n_removed,
            total_violations=self.total_violations,
            pct_violations_removed=100 * n_removed / self.total_violations,
            baseline_impact=self.baseline_impact,
            scenario_impact=new_impact,
            impact_reduction=reduction,
            pct_reduction=pct_reduction,
            segments_improved=int(improved.sum()),
            top_improved_segments=top_improved,
            cost_benefit=cost_benefit,
        )

        logger.info(
            f"  [{name}] removed={n_removed} ({result.pct_violations_removed:.1f}%), "
            f"reduction={pct_reduction:.1f}%, improved={result.segments_improved} segments"
        )
        return result

    def interactive_whatif(self, road_names: list[str]) -> dict:
        """Quick what-if for the dashboard API.

        Returns a dict suitable for JSON serialization.
        """
        result = self.run_scenario(
            name=f"Interactive: {', '.join(road_names[:3])}",
            description=f"User-selected enforcement on {len(road_names)} roads",
            road_names=road_names,
        )
        return {
            "roads": road_names,
            "violations_removed": result.violations_removed,
            "pct_reduction": round(result.pct_reduction, 2),
            "segments_improved": result.segments_improved,
            "top_improved": result.top_improved_segments[:10],
        }


def get_top_roads_by_pis(violations: pd.DataFrame, n: int = 10) -> list[str]:
    """Get top N road names ranked by aggregate PIS."""
    road_pis = (
        violations[violations["road_name"] != "Unnamed"]
        .groupby("road_name")["pis"]
        .sum()
        .sort_values(ascending=False)
    )
    return road_pis.head(n).index.tolist()


def get_top_clusters_by_pis(violations: pd.DataFrame, n: int = 20) -> list[int]:
    """Get top N cluster IDs ranked by aggregate PIS."""
    cluster_pis = (
        violations[violations["cluster_id"] >= 0]
        .groupby("cluster_id")["pis"]
        .sum()
        .sort_values(ascending=False)
    )
    return cluster_pis.head(n).index.tolist()
