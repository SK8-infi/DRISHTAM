"""DRISHTAM — Run Predictive Enforcement Optimizer.

Combines all three engines:
    Engine 1 (Impact) × Engine 2 (What-If) × Engine 3 (Risk)
    → Optimal patrol schedule

Usage:
    python scripts/06_optimize_enforcement.py
"""

from __future__ import annotations

import json
import logging
import time

from drishtam.config import DATA_DIR, PROJECT_ROOT
from drishtam.enforcement_optimizer import EnforcementOptimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    t_start = time.time()
    logger.info("=" * 70)
    logger.info("DRISHTAM — Predictive Enforcement Optimizer")
    logger.info("  Unifying Engine 1 (Impact) × Engine 2 (What-If) × Engine 3 (Risk)")
    logger.info("=" * 70)

    optimizer = EnforcementOptimizer()

    # ===== 1. Primary optimization: 50 officers =====
    logger.info("\n" + "=" * 70)
    logger.info("SCENARIO 1: Standard deployment (50 officers)")
    logger.info("=" * 70)
    schedule_50 = optimizer.optimize(
        n_officers=50, shifts_per_officer=3, hours_per_shift=2
    )

    # ===== 2. Fleet size comparison =====
    logger.info("\n" + "=" * 70)
    logger.info("SCENARIO 2: Fleet size comparison (diminishing returns)")
    logger.info("=" * 70)
    fleet_df = optimizer.compare_fleet_sizes(
        fleet_sizes=[10, 25, 50, 75, 100, 150, 200]
    )

    # ===== 3. Save results =====
    # Main schedule
    schedule_json = optimizer.to_json(schedule_50)
    schedule_path = DATA_DIR / "enforcement_schedule.json"
    with open(schedule_path, "w") as f:
        json.dump(schedule_json, f, indent=2, default=str)
    logger.info(f"\n✅ Schedule saved: {schedule_path}")

    # Fleet comparison
    fleet_path = DATA_DIR / "fleet_comparison.json"
    fleet_df.to_json(fleet_path, orient="records", indent=2)
    logger.info(f"✅ Fleet comparison: {fleet_path}")

    # ===== 4. Print summary =====
    logger.info("\n" + "=" * 70)
    logger.info("ENFORCEMENT INTELLIGENCE SUMMARY")
    logger.info("=" * 70)

    logger.info(f"\n  🏆 OPTIMAL SCHEDULE (50 officers × 3 shifts × 2h):")
    logger.info(f"     Roads covered: {schedule_50.coverage_roads}")
    logger.info(f"     Expected ROI: {schedule_50.total_expected_roi:.2f}")
    logger.info(f"     Impact prevented: {schedule_50.pct_impact_prevented:.3f}%")
    logger.info(f"     Violations deterred: {schedule_50.total_violations_prevented:.0f}/day")
    logger.info(f"     Lift over random: {schedule_50.lift_over_random:.1f}×")

    # Peak vs off-peak
    peak = optimizer.get_peak_hour_schedule(schedule_50)
    logger.info(f"\n  ⏰ PEAK HOUR DEPLOYMENT:")
    logger.info(f"     {peak['pct_peak']:.0f}% of assignments during peak hours")
    logger.info(f"     Peak roads: {peak['peak_roads'][:10]}")

    # Top 10 assignments by ROI
    logger.info(f"\n  🎯 TOP 10 PATROL ASSIGNMENTS:")
    logger.info(f"     {'Officer':>8} {'Road':<30} {'Time':>12} {'ROI':>8} {'P(viol)':>8}")
    logger.info("     " + "-" * 70)
    top10 = sorted(schedule_50.assignments, key=lambda a: -a.expected_roi)[:10]
    for a in top10:
        logger.info(
            f"     {a.officer_id:>8} {a.road_name:<30} "
            f"{a.hour_start:02d}:00-{a.hour_end:02d}:00 "
            f"{a.expected_roi:>8.4f} {a.violation_prob:>8.3f}"
        )

    # Hourly heatmap
    logger.info(f"\n  📊 HOURLY DEPLOYMENT HEATMAP:")
    logger.info(f"     {'Hour':>6} {'Officers':>10} {'ROI':>10}")
    logger.info("     " + "-" * 30)
    for h in range(24):
        n_off = schedule_50.hourly_officers.get(h, 0)
        roi = schedule_50.hourly_roi.get(h, 0)
        bar = "█" * min(n_off, 40)
        logger.info(f"     {h:02d}:00 {n_off:>10} {roi:>10.3f}  {bar}")

    # Fleet comparison
    logger.info(f"\n  📈 DIMINISHING RETURNS CURVE:")
    logger.info(f"     {'Officers':>10} {'Roads':>8} {'ROI':>10} {'Marginal':>10}")
    logger.info("     " + "-" * 42)
    for _, r in fleet_df.iterrows():
        logger.info(
            f"     {int(r['officers']):>10} {int(r['roads_covered']):>8} "
            f"{r['total_roi']:>10.2f} {r['marginal_roi']:>10.4f}"
        )

    elapsed = time.time() - t_start
    logger.info(f"\n  Total time: {elapsed:.1f}s")

    # ===== 5. Key takeaway =====
    logger.info(f"\n{'='*70}")
    logger.info("KEY TAKEAWAY FOR PRESENTATION:")
    logger.info(f"{'='*70}")
    logger.info(
        f"\n  \"With {schedule_50.n_officers} officers deployed using our AI-optimized"
        f"\n   schedule, we can cover {schedule_50.coverage_roads} high-impact roads"
        f"\n   and achieve {schedule_50.lift_over_random:.0f}× better outcomes than"
        f"\n   random patrol assignment.\""
    )


if __name__ == "__main__":
    main()
