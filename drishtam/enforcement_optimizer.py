"""DRISHTAM — Predictive Enforcement Optimizer.

The "crown jewel" that unifies all three engines into a closed-loop
enforcement intelligence system.

For each (road, hour) pair, computes:
    Expected_ROI = P(violation) × Impact(road) × Reduction(road)

Then solves the officer allocation problem:
    "Given N officers across 24 hours, where should each go?"

This enables PROACTIVE enforcement — deploy before violations happen,
at the locations where preventing them has maximum traffic benefit.

Usage:
    from drishtam.enforcement_optimizer import EnforcementOptimizer
    opt = EnforcementOptimizer()
    schedule = opt.optimize(n_officers=50, shifts_per_officer=3)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from drishtam.config import DATA_DIR, ENRICHED_DATA_PATH, PROJECT_ROOT

logger = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "models"


@dataclass
class PatrolAssignment:
    """A single patrol assignment."""
    officer_id: int
    road_name: str
    seg_idx: int
    hour_start: int
    hour_end: int
    lat: float
    lon: float
    expected_roi: float
    violation_prob: float
    impact_score: float
    reduction_score: float


@dataclass
class EnforcementSchedule:
    """Complete enforcement schedule output."""
    n_officers: int
    shifts_per_officer: int
    hours_per_shift: int
    total_assignments: int
    assignments: list[PatrolAssignment] = field(default_factory=list)
    # Aggregate metrics
    total_expected_roi: float = 0.0
    total_violations_prevented: float = 0.0
    total_impact_prevented: float = 0.0
    pct_impact_prevented: float = 0.0
    coverage_roads: int = 0
    coverage_hours: int = 0
    # Comparison baselines
    random_roi: float = 0.0
    lift_over_random: float = 0.0
    # Per-hour breakdown
    hourly_roi: dict[int, float] = field(default_factory=dict)
    hourly_officers: dict[int, int] = field(default_factory=dict)


class EnforcementOptimizer:
    """Unifies all three engines for optimal patrol allocation."""

    def __init__(self) -> None:
        logger.info("=" * 60)
        logger.info("Initializing Enforcement Optimizer")
        logger.info("  Loading all three engine outputs...")
        logger.info("=" * 60)

        self._load_engine1()
        self._load_engine2()
        self._load_engine3()
        self._build_roi_matrix()

    def _load_engine1(self) -> None:
        """Engine 1: Impact prediction per segment."""
        self.segments = pd.read_parquet(MODELS_DIR / "segment_predictions.parquet")
        logger.info(f"  Engine 1: {len(self.segments)} segments with impact predictions")

        # Normalize impact to [0, 1]
        impact = self.segments["impact_gbm"].values
        self.impact_raw = impact.copy()
        self.impact_norm = impact / (impact.max() + 1e-10)

    def _load_engine2(self) -> None:
        """Engine 2: Counterfactual reduction per road."""
        scenarios_path = DATA_DIR / "counterfactual_scenarios.json"
        with open(scenarios_path) as f:
            data = json.load(f)

        self.baseline_impact = data["metadata"]["baseline_impact"]

        # Build per-road reduction estimates from scenario results
        # Use the per-segment improvements from all scenarios
        road_reduction = {}
        for scenario in data["scenarios"]:
            for seg in scenario.get("top_improved_segments", []):
                rn = seg.get("road_name", "")
                if rn and rn != "Unnamed":
                    improvement = seg.get("improvement", 0)
                    if rn not in road_reduction or improvement > road_reduction[rn]:
                        road_reduction[rn] = improvement

        self.road_reduction = road_reduction
        logger.info(f"  Engine 2: {len(road_reduction)} roads with reduction estimates")

    def _load_engine3(self) -> None:
        """Engine 3: Hourly risk predictions."""
        self.risk_df = pd.read_parquet(DATA_DIR / "risk_predictions.parquet")
        logger.info(f"  Engine 3: {len(self.risk_df)} risk predictions ({self.risk_df['hour'].nunique()} hours)")

        # Also load violations for historical probability
        violations = pd.read_parquet(ENRICHED_DATA_PATH)
        hourly_counts = violations.groupby(["road_name", "hour_ist"]).size().unstack(fill_value=0)

        # Convert to probability (rate per day)
        n_days = (violations["created_datetime_ist"].max() - violations["created_datetime_ist"].min()).days
        n_days = max(n_days, 1)
        self.violation_prob = hourly_counts / n_days  # violations per day at this hour
        self.violation_prob = self.violation_prob.clip(upper=1.0)  # cap at 1

        logger.info(f"  Historical: {len(self.violation_prob)} roads, {n_days} days span")

    def _build_roi_matrix(self) -> None:
        """Build the Expected ROI matrix: roads × hours.

        ROI(road, hour) = P(violation | road, hour) × Impact(road) × Reduction(road)
        """
        logger.info("\n  Building Expected ROI matrix...")

        # Get unique roads that appear in risk predictions
        risk_roads = self.risk_df[
            (self.risk_df["road_name"] != "") &
            (self.risk_df["road_name"] != "Unnamed")
        ]["road_name"].unique()

        # Build lookup: road_name → segment info
        seg_lookup = {}
        for _, row in self.segments.iterrows():
            rn = row.get("road_name", "")
            if rn in risk_roads:
                impact = float(row.get("impact_gbm", 0))
                if rn not in seg_lookup or impact > seg_lookup[rn]["impact"]:
                    seg_lookup[rn] = {
                        "seg_idx": int(row["seg_idx"]),
                        "lat": float(row.get("lat", 0)),
                        "lon": float(row.get("lon", 0)),
                        "impact": impact,
                        "tier": int(row.get("tier", 0)),
                    }

        # Build ROI matrix
        road_names = sorted(seg_lookup.keys())
        n_roads = len(road_names)
        road_to_idx = {r: i for i, r in enumerate(road_names)}

        roi_matrix = np.zeros((n_roads, 24), dtype=np.float64)
        prob_matrix = np.zeros((n_roads, 24), dtype=np.float64)
        impact_vector = np.zeros(n_roads, dtype=np.float64)
        reduction_vector = np.zeros(n_roads, dtype=np.float64)

        for i, rn in enumerate(road_names):
            # Impact from Engine 1
            impact_vector[i] = seg_lookup[rn]["impact"]

            # Reduction from Engine 2
            reduction_vector[i] = self.road_reduction.get(rn, impact_vector[i] * 0.5)

            # Probability from Engine 3 (historical)
            for h in range(24):
                if rn in self.violation_prob.index and h in self.violation_prob.columns:
                    prob_matrix[i, h] = float(self.violation_prob.loc[rn, h])

                # ROI = P × Impact × Reduction
                roi_matrix[i, h] = (
                    prob_matrix[i, h] *
                    impact_vector[i] *
                    reduction_vector[i]
                )

        self.road_names = road_names
        self.road_to_idx = road_to_idx
        self.seg_lookup = seg_lookup
        self.roi_matrix = roi_matrix
        self.prob_matrix = prob_matrix
        self.impact_vector = impact_vector
        self.reduction_vector = reduction_vector

        # Stats
        nonzero = (roi_matrix > 0).sum()
        logger.info(f"  ROI matrix: {n_roads} roads × 24 hours = {n_roads * 24} cells")
        logger.info(f"  Non-zero ROI cells: {nonzero} ({100*nonzero/(n_roads*24):.1f}%)")
        logger.info(f"  Max ROI: {roi_matrix.max():.4f}")
        logger.info(f"  Mean ROI (non-zero): {roi_matrix[roi_matrix>0].mean():.4f}")

    def optimize(
        self,
        n_officers: int = 50,
        shifts_per_officer: int = 3,
        hours_per_shift: int = 2,
    ) -> EnforcementSchedule:
        """Solve the officer allocation problem using greedy algorithm.

        Each officer works `shifts_per_officer` shifts of `hours_per_shift`
        hours each. Greedy: assign each shift to the (road, hour_block)
        with highest remaining ROI.

        Args:
            n_officers: number of enforcement officers available
            shifts_per_officer: number of shifts per officer per day
            hours_per_shift: hours per shift

        Returns:
            EnforcementSchedule with optimal assignments
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"OPTIMIZING: {n_officers} officers × {shifts_per_officer} shifts × {hours_per_shift}h")
        logger.info(f"{'='*60}")

        total_shifts = n_officers * shifts_per_officer
        n_roads = len(self.road_names)

        # Build hour-block ROI: aggregate ROI across hours in each block
        n_blocks = 24 // hours_per_shift
        block_roi = np.zeros((n_roads, n_blocks), dtype=np.float64)
        for b in range(n_blocks):
            h_start = b * hours_per_shift
            h_end = h_start + hours_per_shift
            block_roi[:, b] = self.roi_matrix[:, h_start:h_end].sum(axis=1)

        # Track assignments and used capacity
        assigned = np.zeros((n_roads, n_blocks), dtype=bool)
        # Diminishing returns: each additional officer on same road-block
        # gets less benefit (violations already deterred)
        assignment_count = np.zeros((n_roads, n_blocks), dtype=int)

        assignments: list[PatrolAssignment] = []
        officer_schedules: dict[int, list[int]] = {i: [] for i in range(n_officers)}

        # Greedy allocation
        for shift_num in range(total_shifts):
            officer_id = shift_num // shifts_per_officer
            current_shifts = officer_schedules[officer_id]

            # Adjust ROI with diminishing returns
            effective_roi = block_roi / (1 + assignment_count)

            # Mask blocks that this officer already covers (no double-booking)
            officer_mask = np.ones((n_roads, n_blocks), dtype=bool)
            for prev_block in current_shifts:
                officer_mask[:, prev_block] = False

            effective_roi = effective_roi * officer_mask

            # Find best (road, block)
            if effective_roi.max() <= 0:
                break

            best_flat = np.argmax(effective_roi)
            best_road_idx = best_flat // n_blocks
            best_block_idx = best_flat % n_blocks

            road_name = self.road_names[best_road_idx]
            seg_info = self.seg_lookup[road_name]
            h_start = best_block_idx * hours_per_shift
            h_end = h_start + hours_per_shift

            # Violation probability for this block
            prob = float(self.prob_matrix[best_road_idx, h_start:h_end].mean())

            assignment = PatrolAssignment(
                officer_id=officer_id,
                road_name=road_name,
                seg_idx=seg_info["seg_idx"],
                hour_start=h_start,
                hour_end=h_end,
                lat=seg_info["lat"],
                lon=seg_info["lon"],
                expected_roi=float(effective_roi[best_road_idx, best_block_idx]),
                violation_prob=prob,
                impact_score=float(self.impact_vector[best_road_idx]),
                reduction_score=float(self.reduction_vector[best_road_idx]),
            )
            assignments.append(assignment)

            # Update state
            assignment_count[best_road_idx, best_block_idx] += 1
            officer_schedules[officer_id].append(best_block_idx)

            if (shift_num + 1) % 25 == 0 or shift_num < 5:
                logger.info(
                    f"  Shift {shift_num+1:>4}/{total_shifts}: "
                    f"Officer {officer_id:>3} → {road_name:<25} "
                    f"{h_start:02d}:00-{h_end:02d}:00 "
                    f"(ROI={assignment.expected_roi:.4f})"
                )

        # Compute aggregate metrics
        total_roi = sum(a.expected_roi for a in assignments)
        total_violations = sum(a.violation_prob * hours_per_shift for a in assignments)
        total_impact = sum(a.expected_roi for a in assignments)

        # Hourly breakdown
        hourly_roi: dict[int, float] = {}
        hourly_officers: dict[int, int] = {}
        for h in range(24):
            hour_assignments = [
                a for a in assignments if a.hour_start <= h < a.hour_end
            ]
            hourly_roi[h] = sum(a.expected_roi for a in hour_assignments)
            hourly_officers[h] = len(hour_assignments)

        # Coverage
        covered_roads = len(set(a.road_name for a in assignments))
        covered_hours = len(set(h for a in assignments for h in range(a.hour_start, a.hour_end)))

        # Random baseline: what if officers were randomly assigned?
        rng = np.random.RandomState(42)
        random_rois = []
        for _ in range(1000):
            r_road = rng.randint(0, len(self.road_names))
            r_block = rng.randint(0, n_blocks)
            random_rois.append(float(block_roi[r_road, r_block]))
        random_avg = np.mean(random_rois)
        random_total = random_avg * total_shifts
        lift = total_roi / max(random_total, 1e-10)

        # Impact prevented as % of baseline
        pct_prevented = (total_roi / max(self.baseline_impact, 1e-10)) * 100

        schedule = EnforcementSchedule(
            n_officers=n_officers,
            shifts_per_officer=shifts_per_officer,
            hours_per_shift=hours_per_shift,
            total_assignments=len(assignments),
            assignments=assignments,
            total_expected_roi=total_roi,
            total_violations_prevented=total_violations,
            total_impact_prevented=total_impact,
            pct_impact_prevented=pct_prevented,
            coverage_roads=covered_roads,
            coverage_hours=covered_hours,
            random_roi=random_total,
            lift_over_random=lift,
            hourly_roi=hourly_roi,
            hourly_officers=hourly_officers,
        )

        logger.info(f"\n{'='*60}")
        logger.info("OPTIMIZATION RESULTS")
        logger.info(f"{'='*60}")
        logger.info(f"  Total assignments: {len(assignments)}")
        logger.info(f"  Unique roads covered: {covered_roads}")
        logger.info(f"  Hours with coverage: {covered_hours}/24")
        logger.info(f"  Total expected ROI: {total_roi:.2f}")
        logger.info(f"  Random baseline ROI: {random_total:.2f}")
        logger.info(f"  Lift over random: {lift:.1f}×")
        logger.info(f"  Est. impact prevented: {pct_prevented:.2f}% of city-wide")
        logger.info(f"  Est. violations deterred: {total_violations:.0f}/day")

        return schedule

    def compare_fleet_sizes(
        self,
        fleet_sizes: list[int] | None = None,
    ) -> pd.DataFrame:
        """Run optimization for multiple fleet sizes and compare.

        Returns a DataFrame showing diminishing returns curve.
        """
        if fleet_sizes is None:
            fleet_sizes = [10, 20, 30, 50, 75, 100, 150, 200]

        logger.info(f"\n{'='*60}")
        logger.info(f"FLEET SIZE COMPARISON: {fleet_sizes}")
        logger.info(f"{'='*60}")

        rows = []
        for n in fleet_sizes:
            schedule = self.optimize(n_officers=n, shifts_per_officer=3, hours_per_shift=2)
            rows.append({
                "officers": n,
                "total_shifts": schedule.total_assignments,
                "roads_covered": schedule.coverage_roads,
                "total_roi": round(schedule.total_expected_roi, 2),
                "pct_impact": round(schedule.pct_impact_prevented, 3),
                "violations_deterred": round(schedule.total_violations_prevented, 0),
                "lift_over_random": round(schedule.lift_over_random, 1),
                "marginal_roi": 0.0,
            })

        df = pd.DataFrame(rows)
        # Compute marginal ROI (additional ROI per additional officer)
        for i in range(1, len(df)):
            delta_roi = df.loc[i, "total_roi"] - df.loc[i-1, "total_roi"]
            delta_officers = df.loc[i, "officers"] - df.loc[i-1, "officers"]
            df.loc[i, "marginal_roi"] = round(delta_roi / delta_officers, 4)

        logger.info("\n  Fleet size comparison:")
        logger.info(f"  {'Officers':>8} {'Roads':>6} {'ROI':>10} {'%Impact':>8} {'Lift':>6} {'Marginal':>10}")
        logger.info("  " + "-" * 55)
        for _, r in df.iterrows():
            logger.info(
                f"  {r['officers']:>8} {r['roads_covered']:>6} "
                f"{r['total_roi']:>10.2f} {r['pct_impact']:>7.3f}% "
                f"{r['lift_over_random']:>5.1f}× {r['marginal_roi']:>10.4f}"
            )

        return df

    def get_peak_hour_schedule(self, schedule: EnforcementSchedule) -> dict:
        """Extract peak-hour deployment summary for dashboard."""
        peak_hours = [8, 9, 10, 17, 18, 19, 20]
        peak_assignments = [
            a for a in schedule.assignments
            if any(a.hour_start <= h < a.hour_end for h in peak_hours)
        ]

        return {
            "peak_assignments": len(peak_assignments),
            "total_assignments": schedule.total_assignments,
            "pct_peak": round(100 * len(peak_assignments) / max(len(schedule.assignments), 1), 1),
            "peak_roads": list(set(a.road_name for a in peak_assignments)),
            "peak_roi": sum(a.expected_roi for a in peak_assignments),
        }

    def to_json(self, schedule: EnforcementSchedule) -> dict:
        """Convert schedule to JSON-serializable format for API/dashboard."""
        return {
            "metadata": {
                "n_officers": schedule.n_officers,
                "shifts_per_officer": schedule.shifts_per_officer,
                "hours_per_shift": schedule.hours_per_shift,
                "total_assignments": schedule.total_assignments,
            },
            "metrics": {
                "total_roi": round(schedule.total_expected_roi, 2),
                "pct_impact_prevented": round(schedule.pct_impact_prevented, 3),
                "violations_deterred_per_day": round(schedule.total_violations_prevented, 0),
                "roads_covered": schedule.coverage_roads,
                "lift_over_random": round(schedule.lift_over_random, 1),
            },
            "hourly_deployment": {
                str(h): {
                    "officers": schedule.hourly_officers.get(h, 0),
                    "roi": round(schedule.hourly_roi.get(h, 0), 4),
                }
                for h in range(24)
            },
            "assignments": [
                {
                    "officer_id": a.officer_id,
                    "road_name": a.road_name,
                    "hour_start": a.hour_start,
                    "hour_end": a.hour_end,
                    "lat": a.lat,
                    "lon": a.lon,
                    "expected_roi": round(a.expected_roi, 4),
                    "violation_prob": round(a.violation_prob, 4),
                    "impact_score": round(a.impact_score, 4),
                }
                for a in schedule.assignments
            ],
            "peak_summary": self.get_peak_hour_schedule(schedule),
        }
