"""DRISHTAM Phase 4 — Generate all 12 counterfactual scenarios.

Runs the What-If engine across predefined enforcement scenarios
and saves results to data/counterfactual_scenarios.json.

Usage:
    python scripts/05_generate_counterfactuals.py
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from drishtam.config import DATA_DIR, ENRICHED_DATA_PATH
from drishtam.counterfactual import (
    WhatIfEngine,
    get_top_clusters_by_pis,
    get_top_roads_by_pis,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    t_start = time.time()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 4 — Counterfactual What-If Scenarios")
    logger.info("=" * 70)

    engine = WhatIfEngine()
    violations = engine.violations

    # Pre-compute road and cluster rankings
    top10_roads = get_top_roads_by_pis(violations, 10)
    top50_roads = get_top_roads_by_pis(violations, 50)
    top20_clusters = get_top_clusters_by_pis(violations, 20)

    logger.info(f"Top 10 roads: {top10_roads[:5]}...")
    logger.info(f"Top 20 clusters: {top20_clusters[:5]}...")

    # ===== Define all 12 scenarios =====
    scenarios = [
        {
            "name": "S1: Top 10 Named Roads",
            "description": "Enforce parking on the 10 roads with highest aggregate PIS",
            "criteria": {"road_names": top10_roads},
        },
        {
            "name": "S2: Top 50 Named Roads",
            "description": "Enforce parking on the 50 roads with highest aggregate PIS",
            "criteria": {"road_names": top50_roads},
        },
        {
            "name": "S3: All Critical PIS (>80)",
            "description": "Remove all violations with PIS score > 80",
            "criteria": {"pis_min": 80},
        },
        {
            "name": "S4: All >25% Blockage",
            "description": "Remove all violations blocking >25% of road capacity",
            "criteria": {"capacity_blocked_min": 25},
        },
        {
            "name": "S5: BSF STS Road Only",
            "description": "Enforce parking on BSF STS Road (the #1 hotspot)",
            "criteria": {"road_names": ["BSF STS Road"]},
        },
        {
            "name": "S6: Evening Peak Enforcement",
            "description": "Add enforcement during 15:30-20:30 IST (the gap)",
            "criteria": {"hour_range": (15, 20)},
        },
        {
            "name": "S7: Top 20 HDBSCAN Clusters",
            "description": "Enforce the 20 most impactful violation clusters",
            "criteria": {"cluster_ids": top20_clusters},
        },
        {
            "name": "S8: Remove All Car Violations",
            "description": "Remove all CAR parking violations",
            "criteria": {"vehicle_types": ["CAR"]},
        },
        {
            "name": "S9: Remove Link Road Violations",
            "description": "Enforce parking on all link/ramp roads",
            "criteria": {"is_link_road": True},
        },
        {
            "name": "S10: Upgrade Top 5 Roads (4-lane)",
            "description": "Simulate widening top 5 roads to 4 lanes (reduces blockage impact)",
            "criteria": {"road_names": top10_roads[:5]},
        },
        {
            "name": "S11: Repeat Offenders (11+ violations)",
            "description": "Remove violations from chronic repeat offenders (≥11 violations)",
            "criteria": {"repeat_count_min": 11},
        },
        {
            "name": "S12: 100 Officers Optimal Deployment",
            "description": "Deploy 100 officers to top 100 roads by PIS density (PIS/km)",
            "criteria": {"road_names": get_top_roads_by_pis(violations, 100)},
        },
    ]

    # ===== Run all scenarios =====
    results = []
    logger.info(f"\nRunning {len(scenarios)} scenarios...")
    logger.info("-" * 70)

    for scenario in scenarios:
        t0 = time.time()
        result = engine.run_scenario(
            name=scenario["name"],
            description=scenario["description"],
            **scenario["criteria"],
        )
        elapsed = time.time() - t0
        results.append(result)
        logger.info(
            f"  {result.name:<40} | "
            f"removed={result.violations_removed:>6} ({result.pct_violations_removed:>5.1f}%) | "
            f"reduction={result.pct_reduction:>5.1f}% | "
            f"{elapsed:.1f}s"
        )

    # ===== Sanity checks =====
    logger.info("\n" + "=" * 70)
    logger.info("SANITY CHECKS")
    logger.info("=" * 70)

    # Check monotonicity: S1 (10 roads) < S2 (50 roads) < S12 (100 roads)
    r_s1 = results[0].pct_reduction
    r_s2 = results[1].pct_reduction
    r_s12 = results[11].pct_reduction
    mono_ok = r_s1 <= r_s2 <= r_s12
    logger.info(f"  Monotonicity (S1 < S2 < S12): {r_s1:.1f}% < {r_s2:.1f}% < {r_s12:.1f}% → {'✅' if mono_ok else '⚠️'}")

    # Check BSF STS Road (S5) has small but non-zero effect
    r_s5 = results[4].pct_reduction
    bsf_ok = 0 < r_s5 < 20
    logger.info(f"  BSF STS Road (S5): {r_s5:.1f}% → {'✅' if bsf_ok else '⚠️'} (expected 0-20%)")

    # Check all results are reasonable
    for r in results:
        if not (0 <= r.pct_reduction <= 100):
            logger.warning(f"  ⚠️ {r.name}: reduction={r.pct_reduction:.1f}% out of range!")

    # ===== Save results =====
    output_path = DATA_DIR / "counterfactual_scenarios.json"
    output = {
        "metadata": {
            "total_violations": engine.total_violations,
            "total_segments": len(engine.segments),
            "baseline_impact": engine.baseline_impact,
            "baseline_affected": engine.baseline_affected,
            "baseline_critical": engine.baseline_critical,
        },
        "scenarios": [asdict(r) for r in results],
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info(f"\nSaved: {output_path}")

    # ===== Print summary table =====
    logger.info("\n" + "=" * 70)
    logger.info("SCENARIO SUMMARY — THE REDUCTION LADDER")
    logger.info("=" * 70)
    logger.info(
        f"{'Scenario':<40} {'Removed':>8} {'%Viols':>7} {'%Reduction':>11} {'Cost-Eff':>10}"
    )
    logger.info("-" * 76)

    ranked = sorted(results, key=lambda r: -r.pct_reduction)
    for r in ranked:
        logger.info(
            f"{r.name:<40} {r.violations_removed:>8} {r.pct_violations_removed:>6.1f}% "
            f"{r.pct_reduction:>10.1f}% {r.cost_benefit:>10.6f}"
        )

    elapsed_total = time.time() - t_start
    logger.info(f"\nTotal time: {elapsed_total:.1f}s")


if __name__ == "__main__":
    main()
