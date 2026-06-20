"""DRISHTAM Phase 4 — Train Risk Forecaster with comprehensive model sweep.

Runs:
1. Feature engineering (27D temporal + spatial + historical features)
2. 7+ model types (HistGBM, XGBoost, LightGBM, RF, ExtraTrees, MLP, Ridge)
3. Feature group ablation (drop each group, test each alone)
4. Feature combination sweep
5. Ensemble blending (top-2, top-3, weighted)
6. Save best model + risk predictions

Usage:
    python scripts/04_train_forecaster.py
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from drishtam.config import DATA_DIR, PROJECT_ROOT
from drishtam.risk_forecaster import RiskForecaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "models"


def main() -> None:
    t_start = time.time()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 4 — Risk Forecaster Training")
    logger.info("=" * 70)

    # Initialize
    forecaster = RiskForecaster()

    # Build features (vectorized — should take ~5s)
    X, y, feature_names = forecaster.build_features()
    logger.info(f"Features: {X.shape}, {len(feature_names)} names")
    logger.info(f"Target: mean={y.mean():.1f}, max={y.max():.1f}, nonzero={int((y>0).sum())}")

    # Feature correlations
    logger.info("\n--- Feature correlations with risk_score ---")
    from scipy.stats import spearmanr
    cors = []
    for i, name in enumerate(feature_names):
        r, _ = spearmanr(X[:, i], y)
        if not np.isnan(r):
            cors.append((name, r))
    cors.sort(key=lambda x: -abs(x[1]))
    for name, r in cors[:15]:
        logger.info(f"  {name:>20}: r={r:+.4f}")

    # ===== Run comprehensive sweep =====
    logger.info(f"\n{'='*70}")
    logger.info("Starting comprehensive model sweep...")
    logger.info(f"{'='*70}")
    results = forecaster.run_full_sweep(X, y)

    # ===== Print final leaderboard =====
    logger.info(f"\n{'='*70}")
    logger.info("FINAL LEADERBOARD")
    logger.info(f"{'='*70}")
    logger.info(
        f"{'#':>3} {'Model':<50} {'Feats':<20} {'r':>7} {'RMSE':>9} {'R²':>7} {'Time':>7}"
    )
    logger.info("-" * 110)

    sorted_results = sorted(results, key=lambda r: -r.test_spearman)
    for rank, r in enumerate(sorted_results, 1):
        marker = " ★" if rank == 1 else ""
        logger.info(
            f"{rank:>3} {r.name:<50} {r.features:<20} "
            f"{r.test_spearman:>7.4f} {r.test_rmse:>9.1f} {r.test_r2:>7.4f} "
            f"{r.train_time:>6.1f}s{marker}"
        )

    best = sorted_results[0]
    logger.info(f"\n★ BEST MODEL: {best.name}")
    logger.info(f"  Spearman r: {best.test_spearman:.4f}")
    logger.info(f"  RMSE: {best.test_rmse:.1f}")
    logger.info(f"  R²: {best.test_r2:.4f}")

    # ===== Save best model =====
    if best.model is not None:
        model_path = MODELS_DIR / "risk_forecaster_best.pkl"
        joblib.dump(best.model, model_path)
        logger.info(f"  Saved: {model_path}")

    # ===== Generate risk predictions for active segments =====
    logger.info(f"\n{'='*70}")
    logger.info("Generating hourly risk maps...")
    logger.info(f"{'='*70}")

    active_segs = forecaster.segments[forecaster.segments["violation_count"] > 0].reset_index(drop=True)
    n_active = len(active_segs)
    logger.info(f"  Active segments: {n_active}")

    risk_rows = []
    for hour in range(24):
        for _, seg in active_segs.iterrows():
            road_name = seg.get("road_name", "")
            rs = forecaster.road_stats[forecaster.road_stats["road_name"] == road_name]
            if len(rs) > 0:
                rs = rs.iloc[0]
                hourly_rate = (
                    forecaster.hourly_counts.loc[road_name, hour]
                    if road_name in forecaster.hourly_counts.index
                    and hour in forecaster.hourly_counts.columns
                    else 0
                )
                risk = float(hourly_rate * rs.get("mean_pis", 0))
            else:
                risk = 0.0

            risk_rows.append({
                "seg_idx": int(seg["seg_idx"]),
                "road_name": str(road_name),
                "lat": float(seg.get("lat", 0)),
                "lon": float(seg.get("lon", 0)),
                "hour": hour,
                "risk_score": risk,
                "risk_band": (
                    "critical" if risk > 50
                    else "high" if risk > 20
                    else "medium" if risk > 5
                    else "low"
                ),
            })
        logger.info(f"  Hour {hour:02d}/23 done")

    risk_df = pd.DataFrame(risk_rows)
    risk_path = DATA_DIR / "risk_predictions.parquet"
    risk_df.to_parquet(risk_path, index=False)
    logger.info(f"  ✅ Saved: {risk_path} ({risk_df.shape})")

    # Alerts
    alerts = forecaster.generate_alerts(risk_df)
    alerts_path = DATA_DIR / "risk_alerts.json"
    with open(alerts_path, "w") as f:
        json.dump(alerts, f, indent=2, default=str)
    logger.info(f"  ✅ Saved: {alerts_path}")

    # Summary
    summary = {
        "best_model": best.name,
        "best_spearman_r": round(best.test_spearman, 4),
        "best_rmse": round(best.test_rmse, 4),
        "best_r2": round(best.test_r2, 4),
        "n_models_tested": len(results),
        "n_features": best.n_features,
        "feature_names": feature_names,
        "active_segments": int(n_active),
        "top_5_models": [
            {"name": r.name, "r": round(r.test_spearman, 4), "features": r.features}
            for r in sorted_results[:5]
        ],
    }
    summary_path = DATA_DIR / "risk_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"  ✅ Saved: {summary_path}")

    elapsed = time.time() - t_start
    logger.info(f"\n{'='*70}")
    logger.info(f"TOTAL TIME: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"{'='*70}")


if __name__ == "__main__":
    main()
