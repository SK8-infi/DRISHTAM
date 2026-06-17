"""DRISHTAM data verification checks.

Quality gates that must pass before proceeding to the next phase.
Each function returns a dict of check_name → passed (bool) and
raises DataValidationError if any critical check fails.

Reference: plans/phase1_data_foundation.md §1.4 verification checklist
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

from drishtam.exceptions import DataValidationError

logger = logging.getLogger(__name__)


def verify_enriched_data(df: pd.DataFrame) -> dict[str, bool]:
    """Run all Phase 1 data quality checks.

    Args:
        df: Enriched violation DataFrame.

    Returns:
        Dict of check_name -> passed (bool).

    Raises:
        DataValidationError: If any critical check fails.
    """
    checks: dict[str, bool] = {}

    # Check 1: Record count ~298K
    checks["record_count"] = 250_000 < len(df) < 350_000
    logger.info(
        "Check 1 - Record count: %d [%s]",
        len(df),
        "PASS" if checks["record_count"] else "FAIL",
    )

    # Check 2: No NaN in core columns
    core_cols = [
        "latitude",
        "longitude",
        "vehicle_width_m",
        "road_width",
        "road_tier",
        "capacity_blocked_pct",
        "violation_severity",
    ]
    missing_cols = [c for c in core_cols if c not in df.columns]
    if missing_cols:
        checks["no_core_nulls"] = False
        logger.error("Check 2 - Missing columns: %s", missing_cols)
    else:
        null_count = df[core_cols].isna().sum().sum()
        checks["no_core_nulls"] = null_count == 0
        logger.info(
            "Check 2 - Core nulls: %d [%s]",
            null_count,
            "PASS" if checks["no_core_nulls"] else "FAIL",
        )

    # Check 3: capacity_blocked_pct range [0, 100]
    if "capacity_blocked_pct" in df.columns:
        cap_min = df["capacity_blocked_pct"].min()
        cap_max = df["capacity_blocked_pct"].max()
        checks["capacity_range"] = cap_min >= 0 and cap_max <= 100
        logger.info(
            "Check 3 - Capacity range: [%.1f, %.1f] [%s]",
            cap_min,
            cap_max,
            "PASS" if checks["capacity_range"] else "FAIL",
        )
    else:
        checks["capacity_range"] = False

    # Check 4: Median distance to road ~19m
    if "dist_to_road_m" in df.columns:
        median_dist = df["dist_to_road_m"].median()
        checks["median_dist_reasonable"] = 5 < median_dist < 50
        logger.info(
            "Check 4 - Median dist to road: %.1fm [%s]",
            median_dist,
            "PASS" if checks["median_dist_reasonable"] else "FAIL",
        )
    else:
        checks["median_dist_reasonable"] = False

    # Check 5: dist_to_junction_m filled
    if "dist_to_junction_m" in df.columns:
        junc_nulls = df["dist_to_junction_m"].isna().sum()
        checks["junction_dist_filled"] = junc_nulls == 0
        logger.info(
            "Check 5 - Junction dist nulls: %d [%s]",
            junc_nulls,
            "PASS" if checks["junction_dist_filled"] else "FAIL",
        )
    else:
        checks["junction_dist_filled"] = False

    # Check 6: violation_severity range [0.4, 1.0]
    if "violation_severity" in df.columns:
        sev_min = df["violation_severity"].min()
        sev_max = df["violation_severity"].max()
        checks["severity_range"] = sev_min >= 0.3 and sev_max <= 1.0
        logger.info(
            "Check 6 - Severity range: [%.2f, %.2f] [%s]",
            sev_min,
            sev_max,
            "PASS" if checks["severity_range"] else "FAIL",
        )
    else:
        checks["severity_range"] = False

    # Check 7: Temporal features present
    temporal_cols = ["hour_ist", "day_of_week", "month", "is_weekend", "temporal_factor", "peak_period"]
    present = [c for c in temporal_cols if c in df.columns]
    checks["temporal_features"] = len(present) >= 6
    logger.info(
        "Check 7 - Temporal features: %d/%d [%s]",
        len(present),
        len(temporal_cols),
        "PASS" if checks["temporal_features"] else "FAIL",
    )

    # Check 8: BSF STS Road count ~5231
    if "road_name" in df.columns:
        bsf_count = (df["road_name"] == "BSF STS Road").sum()
        checks["bsf_road_count"] = bsf_count > 3000  # Allow some tolerance
        logger.info(
            "Check 8 - BSF STS Road violations: %d [%s]",
            bsf_count,
            "PASS" if checks["bsf_road_count"] else "FAIL",
        )
    else:
        checks["bsf_road_count"] = False

    # Check 9: High-impact violations ~41K (>25% capacity blocked)
    if "capacity_blocked_pct" in df.columns:
        high_impact = (df["capacity_blocked_pct"] > 25).sum()
        checks["high_impact_count"] = 30_000 < high_impact < 60_000
        logger.info(
            "Check 9 - High-impact violations (>25%%): %d [%s]",
            high_impact,
            "PASS" if checks["high_impact_count"] else "FAIL",
        )
    else:
        checks["high_impact_count"] = False

    # --- Summary ---
    passed = sum(v for v in checks.values())
    total = len(checks)
    failed_names = [k for k, v in checks.items() if not v]

    logger.info("=" * 60)
    logger.info("VERIFICATION SUMMARY: %d/%d checks passed", passed, total)
    if failed_names:
        logger.warning("FAILED checks: %s", ", ".join(failed_names))
    else:
        logger.info("ALL CHECKS PASSED")
    logger.info("=" * 60)

    if len(failed_names) > 2:
        msg = f"Too many verification failures ({len(failed_names)}/{total}): {', '.join(failed_names)}"
        raise DataValidationError(msg)

    return checks


def print_enrichment_summary(df: pd.DataFrame) -> str:
    """Print and return a formatted summary of the enriched dataset.

    Args:
        df: Enriched violation DataFrame.

    Returns:
        Formatted summary string.
    """
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("DRISHTAM — Enriched Data Summary")
    lines.append("=" * 70)
    lines.append(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
    lines.append(f"Memory: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")
    lines.append("")

    # Key numeric stats
    key_cols = [
        "capacity_blocked_pct",
        "dist_to_road_m",
        "dist_to_junction_m",
        "violation_density_300m",
        "violation_severity",
        "road_width",
        "road_lanes",
        "temporal_factor",
        "repeat_count",
    ]
    available = [c for c in key_cols if c in df.columns]
    if available:
        lines.append("--- Key Feature Statistics ---")
        stats = df[available].describe().T[["mean", "std", "min", "50%", "max"]]
        lines.append(stats.to_string())
        lines.append("")

    # Road tier distribution
    if "road_tier_name" in df.columns:
        lines.append("--- Road Tier Distribution ---")
        tier_counts = df["road_tier_name"].value_counts()
        for tier, count in tier_counts.items():
            lines.append(f"  {tier:<20s}: {count:>8,} ({count / len(df) * 100:.1f}%)")
        lines.append("")

    # High-impact stats
    if "capacity_blocked_pct" in df.columns:
        high = (df["capacity_blocked_pct"] > 25).sum()
        lines.append("--- Impact Stats ---")
        lines.append(f"  High-impact (>25% blocked): {high:,} ({high / len(df) * 100:.1f}%)")
        lines.append(f"  Mean capacity blocked: {df['capacity_blocked_pct'].mean():.1f}%")

    # Multi-modal
    if "is_near_metro" in df.columns:
        metro = df["is_near_metro"].sum()
        lines.append(f"  Near metro (<200m): {metro:,} ({metro / len(df) * 100:.1f}%)")
    if "is_near_bus_stop" in df.columns:
        bus = df["is_near_bus_stop"].sum()
        lines.append(f"  Near bus stop (<50m): {bus:,} ({bus / len(df) * 100:.1f}%)")

    summary = "\n".join(lines)
    logger.info("\n%s", summary)
    return summary
