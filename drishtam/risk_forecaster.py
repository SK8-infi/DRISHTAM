"""DRISHTAM Engine 3 — Risk Forecaster.

Predicts which road segments will have parking violations at each hour,
using temporal, spatial, historical, and neighborhood features.

Includes comprehensive model sweep:
    - Feature group ablation
    - 7 model types (HistGBM, XGBoost, LightGBM, RF, MLP, Ridge, ExtraTrees)
    - Ensemble blending

Usage:
    from drishtam.risk_forecaster import RiskForecaster
    forecaster = RiskForecaster()
    forecaster.train()
    risk_maps = forecaster.generate_risk_maps()
"""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from drishtam.config import ENRICHED_DATA_PATH, PROJECT_ROOT

logger = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "models"


@dataclass
class ModelResult:
    """Result of a model training run."""
    name: str
    features: str
    n_features: int
    test_rmse: float
    test_mae: float
    test_r2: float
    test_spearman: float
    train_time: float
    model: Any = None


class RiskForecaster:
    """Comprehensive risk forecaster with model sweep."""

    def __init__(self) -> None:
        logger.info("Initializing Risk Forecaster...")
        self._load_data()
        self._build_segment_profiles()

    def _load_data(self) -> None:
        """Load violations and segment predictions."""
        self.violations = pd.read_parquet(ENRICHED_DATA_PATH)
        self.segments = pd.read_parquet(MODELS_DIR / "segment_predictions.parquet")
        self.betweenness = np.load(MODELS_DIR / "seg_betweenness.npy")

        logger.info(f"  Violations: {len(self.violations)}")
        logger.info(f"  Segments: {len(self.segments)}")

    def _build_segment_profiles(self) -> None:
        """Build per-segment historical profiles from violation data."""
        v = self.violations.copy()

        # Group by road_name to get segment-level stats
        road_stats = v.groupby("road_name").agg(
            total_violations=("id", "count"),
            mean_pis=("pis", "mean"),
            max_pis=("pis", "max"),
            mean_cap_blocked=("capacity_blocked_pct", "mean"),
            mean_severity=("violation_severity", "mean"),
            unique_vehicles=("vehicle_number", "nunique"),
            pct_peak_morning=("is_peak_morning", "mean"),
            pct_peak_evening=("is_peak_evening", "mean"),
            pct_weekend=("is_weekend", "mean"),
            mean_density_300m=("violation_density_300m", "mean"),
            mean_density_500m=("violation_density_500m", "mean"),
            pct_car=("vehicle_type_clean", lambda x: (x == "CAR").mean()),
            pct_two_wheeler=("vehicle_type_clean", lambda x: (x.isin(["SCOOTER", "MOTOR CYCLE", "MOPED"])).mean()),
        ).reset_index()

        # Hourly profile per road
        hourly_counts = v.groupby(["road_name", "hour_ist"]).size().unstack(fill_value=0)
        hourly_pcts = hourly_counts.div(hourly_counts.sum(axis=1), axis=0)
        road_stats["peak_hour"] = hourly_counts.idxmax(axis=1).values
        road_stats["hourly_entropy"] = (
            -(hourly_pcts * np.log2(hourly_pcts.clip(1e-10))).sum(axis=1).values
        )

        self.road_stats = road_stats
        self.hourly_counts = hourly_counts
        logger.info(f"  Road profiles: {len(road_stats)} roads")

    def build_features(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Build (segment × hour) feature matrix — VECTORIZED.

        Returns:
            X: feature matrix (n_samples × n_features)
            y: target (risk_score)
            feature_names: list of feature names
        """
        logger.info("Building risk features (vectorized)...")
        t0 = time.time()
        segs = self.segments

        # Only include segments with at least 1 violation
        active_segs = segs[segs["violation_count"] > 0].copy()
        logger.info(f"  Active segments (with violations): {len(active_segs)}")

        # Merge road stats
        active_segs = active_segs.merge(
            self.road_stats, on="road_name", how="left"
        ).fillna(0)
        n_segs = len(active_segs)

        # Pre-compute hourly rates matrix (n_segs × 24)
        logger.info("  Building hourly rate matrix...")
        hourly_matrix = np.zeros((n_segs, 24), dtype=np.float32)
        for i, (_, seg) in enumerate(active_segs.iterrows()):
            rn = seg["road_name"]
            if rn in self.hourly_counts.index:
                for h in range(24):
                    if h in self.hourly_counts.columns:
                        hourly_matrix[i, h] = self.hourly_counts.loc[rn, h]

        # Extract segment-level features once (n_segs,)
        tier = active_segs["tier"].values.astype(np.float32)
        lanes = active_segs["lanes"].values.astype(np.float32)
        log_length = np.log1p(active_segs["length_m"].values).astype(np.float32)
        bc = active_segs["betweenness"].values.astype(np.float32) * 1000
        is_major = (tier >= 3).astype(np.float32)
        log_total_v = np.log1p(active_segs["total_violations"].values).astype(np.float32)
        mean_pis = active_segs["mean_pis"].values.astype(np.float32)
        max_pis = active_segs["max_pis"].values.astype(np.float32)
        mean_cap = active_segs["mean_cap_blocked"].values.astype(np.float32)
        density_300 = active_segs["mean_density_300m"].values.astype(np.float32)
        pct_car = active_segs["pct_car"].values.astype(np.float32)
        hourly_entropy = active_segs["hourly_entropy"].values.astype(np.float32)
        pct_peak_eve = active_segs["pct_peak_evening"].values.astype(np.float32)
        gbm_pred = active_segs["impact_gbm"].values.astype(np.float32)

        # Build full feature matrix (n_segs * 24, 27)
        logger.info("  Assembling feature matrix...")
        total_rows = n_segs * 24
        X = np.zeros((total_rows, 27), dtype=np.float32)
        y = np.zeros(total_rows, dtype=np.float32)

        for h in range(24):
            start = h * n_segs
            end = start + n_segs
            hr = hourly_matrix[:, h]
            log_hr = np.log1p(hr)

            is_peak_am = 1.0 if 8 <= h <= 10 else 0.0
            is_peak_pm = 1.0 if 17 <= h <= 20 else 0.0
            is_night = 1.0 if h < 6 or h > 22 else 0.0

            # Temporal
            X[start:end, 0] = np.sin(2 * np.pi * h / 24)
            X[start:end, 1] = np.cos(2 * np.pi * h / 24)
            X[start:end, 2] = is_peak_am
            X[start:end, 3] = is_peak_pm
            X[start:end, 4] = is_night
            # Spatial
            X[start:end, 5] = tier
            X[start:end, 6] = lanes
            X[start:end, 7] = log_length
            X[start:end, 8] = bc
            X[start:end, 9] = is_major
            # Historical
            X[start:end, 10] = log_total_v
            X[start:end, 11] = mean_pis
            X[start:end, 12] = max_pis
            X[start:end, 13] = mean_cap
            X[start:end, 14] = log_hr
            X[start:end, 15] = density_300
            X[start:end, 16] = pct_car
            X[start:end, 17] = hourly_entropy
            X[start:end, 18] = pct_peak_eve
            # GBM prediction
            X[start:end, 19] = gbm_pred
            # Interactions
            X[start:end, 20] = tier * log_hr
            X[start:end, 21] = bc * mean_pis
            X[start:end, 22] = is_peak_pm * log_hr
            X[start:end, 23] = tier * mean_cap
            X[start:end, 24] = log_total_v * is_peak_pm
            X[start:end, 25] = lanes * mean_cap
            X[start:end, 26] = gbm_pred * log_hr
            # Target
            y[start:end] = hr * mean_pis

        X = np.nan_to_num(X, 0.0)
        y = np.nan_to_num(y, 0.0)

        feature_names = [
            "hour_sin", "hour_cos", "is_peak_am", "is_peak_pm", "is_night",
            "tier", "lanes", "log_length", "betweenness", "is_major",
            "log_total_v", "mean_pis", "max_pis", "mean_cap_blocked",
            "log_hourly_rate", "density_300m", "pct_car", "hourly_entropy",
            "pct_peak_evening",
            "gbm_pred",
            "tier×rate", "bc×pis", "peak×rate", "tier×cap", "v×peak",
            "lanes×cap", "gbm×rate",
        ]

        elapsed = time.time() - t0
        logger.info(f"  ✅ Features built in {elapsed:.1f}s: {X.shape}, nonzero={int((y>0).sum())}")
        self._feature_names = feature_names
        self._active_segs = active_segs
        return X, y, feature_names

    def build_feature_groups(self) -> dict[str, list[int]]:
        """Define feature groups for ablation study."""
        return {
            "temporal": [0, 1, 2, 3, 4],
            "spatial": [5, 6, 7, 8, 9],
            "historical": [10, 11, 12, 13, 14, 15, 16, 17, 18],
            "gbm_pred": [19],
            "interactions": [20, 21, 22, 23, 24, 25, 26],
        }

    def temporal_split(
        self, X: np.ndarray, y: np.ndarray, train_ratio: float = 0.7
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Split data by segment (no road leaks into both sets)."""
        n_segs = len(self._active_segs)
        n_hours = 24

        rng = np.random.RandomState(42)
        seg_order = rng.permutation(n_segs)
        n_train = int(n_segs * train_ratio)

        train_segs = seg_order[:n_train]
        test_segs = seg_order[n_train:]

        train_idx = np.concatenate([np.arange(s * n_hours, (s + 1) * n_hours) for s in train_segs])
        test_idx = np.concatenate([np.arange(s * n_hours, (s + 1) * n_hours) for s in test_segs])

        n_total = len(X)
        train_idx = train_idx[train_idx < n_total]
        test_idx = test_idx[test_idx < n_total]

        return X[train_idx], X[test_idx], y[train_idx], y[test_idx]

    def train_model(
        self,
        model: Any,
        name: str,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_group: str = "all",
    ) -> ModelResult:
        """Train a single model and evaluate."""
        logger.info(f"    → Training {name} ({X_train.shape[1]} features, {len(X_train)} rows)...")
        t0 = time.time()
        model.fit(X_train, y_train)
        elapsed = time.time() - t0

        preds = model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        mae = float(mean_absolute_error(y_test, preds))
        r2 = float(r2_score(y_test, preds))
        sr, _ = spearmanr(preds, y_test)
        sr = float(sr) if not np.isnan(sr) else 0.0

        logger.info(
            f"    ✅ {name}: r={sr:.4f} RMSE={rmse:.1f} R²={r2:.4f} ({elapsed:.1f}s)"
        )

        return ModelResult(
            name=name, features=feature_group, n_features=X_train.shape[1],
            test_rmse=rmse, test_mae=mae, test_r2=r2,
            test_spearman=sr, train_time=elapsed, model=model,
        )

    def run_full_sweep(
        self, X: np.ndarray, y: np.ndarray
    ) -> list[ModelResult]:
        """Run comprehensive model sweep."""
        results = []
        X_train, X_test, y_train, y_test = self.temporal_split(X, y)

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        self._scaler = scaler
        self._y_test = y_test

        logger.info(f"  Train: {X_train.shape}, Test: {X_test.shape}")
        logger.info(f"  Target: train mean={y_train.mean():.1f}, test mean={y_test.mean():.1f}")

        # ===== 1. ALL MODELS ON FULL FEATURES =====
        logger.info("\n" + "=" * 70)
        logger.info("SWEEP 1: All model types (full 27 features)")
        logger.info("=" * 70)

        models: dict[str, tuple[Any, bool]] = {
            # (model, needs_scaling)
            "HistGBM": (HistGradientBoostingRegressor(
                max_iter=300, max_depth=6, learning_rate=0.05,
                min_samples_leaf=20, max_bins=255, random_state=42,
            ), False),
            "HistGBM-Deep": (HistGradientBoostingRegressor(
                max_iter=500, max_depth=8, learning_rate=0.03,
                min_samples_leaf=30, max_bins=255, random_state=42,
            ), False),
            "RandomForest": (RandomForestRegressor(
                n_estimators=200, max_depth=12, min_samples_leaf=20,
                max_features="sqrt", n_jobs=-1, random_state=42,
            ), False),
            "ExtraTrees": (ExtraTreesRegressor(
                n_estimators=200, max_depth=12, min_samples_leaf=20,
                max_features="sqrt", n_jobs=-1, random_state=42,
            ), False),
            "Ridge": (Ridge(alpha=1.0), True),
            "MLP": (MLPRegressor(
                hidden_layer_sizes=(128, 64, 32), max_iter=500,
                learning_rate_init=0.001, early_stopping=True,
                validation_fraction=0.15, random_state=42,
            ), True),
        }

        # Try XGBoost (GPU if available)
        try:
            from xgboost import XGBRegressor
            try:
                models["XGBoost-GPU"] = (XGBRegressor(
                    n_estimators=300, max_depth=6, learning_rate=0.05,
                    subsample=0.8, colsample_bytree=0.8,
                    min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0,
                    tree_method="gpu_hist", device="cuda", random_state=42,
                ), False)
                logger.info("  XGBoost GPU mode enabled ✅")
            except Exception:
                models["XGBoost"] = (XGBRegressor(
                    n_estimators=300, max_depth=6, learning_rate=0.05,
                    subsample=0.8, colsample_bytree=0.8,
                    min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0,
                    tree_method="hist", random_state=42,
                ), False)
                logger.info("  XGBoost CPU mode (no GPU)")
        except ImportError:
            logger.info("  XGBoost not installed, skipping")

        # Try LightGBM (GPU if available)
        try:
            from lightgbm import LGBMRegressor
            try:
                models["LightGBM-GPU"] = (LGBMRegressor(
                    n_estimators=300, max_depth=6, learning_rate=0.05,
                    subsample=0.8, colsample_bytree=0.8,
                    min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0,
                    device="gpu", random_state=42, verbose=-1,
                ), False)
                logger.info("  LightGBM GPU mode enabled ✅")
            except Exception:
                models["LightGBM"] = (LGBMRegressor(
                    n_estimators=300, max_depth=6, learning_rate=0.05,
                    subsample=0.8, colsample_bytree=0.8,
                    min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0,
                    random_state=42, verbose=-1,
                ), False)
                logger.info("  LightGBM CPU mode (no GPU)")
        except ImportError:
            logger.info("  LightGBM not installed, skipping")

        for name, (model, needs_scaling) in models.items():
            Xtr = X_train_s if needs_scaling else X_train
            Xte = X_test_s if needs_scaling else X_test
            try:
                result = self.train_model(model, name, Xtr, Xte, y_train, y_test, "all_27")
                results.append(result)
            except Exception as e:
                logger.warning(f"    ❌ {name} failed: {e}")
                # If GPU failed, retry CPU
                if "GPU" in name:
                    cpu_name = name.replace("-GPU", "-CPU")
                    logger.info(f"    Retrying {cpu_name}...")
                    try:
                        if "XGBoost" in name:
                            from xgboost import XGBRegressor
                            cpu_model = XGBRegressor(
                                n_estimators=300, max_depth=6, learning_rate=0.05,
                                subsample=0.8, colsample_bytree=0.8,
                                tree_method="hist", random_state=42,
                            )
                        else:
                            from lightgbm import LGBMRegressor
                            cpu_model = LGBMRegressor(
                                n_estimators=300, max_depth=6, learning_rate=0.05,
                                subsample=0.8, colsample_bytree=0.8,
                                random_state=42, verbose=-1,
                            )
                        result = self.train_model(cpu_model, cpu_name, Xtr, Xte, y_train, y_test, "all_27")
                        results.append(result)
                    except Exception as e2:
                        logger.warning(f"    ❌ {cpu_name} also failed: {e2}")

        # ===== 2. FEATURE GROUP ABLATION (using HistGBM) =====
        logger.info("\n" + "=" * 70)
        logger.info("SWEEP 2: Feature group ablation (HistGBM)")
        logger.info("=" * 70)

        groups = self.build_feature_groups()
        all_indices = list(range(X.shape[1]))

        for group_name, group_indices in groups.items():
            keep = [i for i in all_indices if i not in group_indices]
            if not keep:
                continue
            model = HistGradientBoostingRegressor(
                max_iter=200, max_depth=6, learning_rate=0.05,
                min_samples_leaf=20, random_state=42,
            )
            result = self.train_model(
                model, f"Drop-{group_name}",
                X_train[:, keep], X_test[:, keep],
                y_train, y_test, f"drop_{group_name}",
            )
            results.append(result)

        for group_name, group_indices in groups.items():
            if not group_indices:
                continue
            model = HistGradientBoostingRegressor(
                max_iter=200, max_depth=6, learning_rate=0.05,
                min_samples_leaf=20, random_state=42,
            )
            result = self.train_model(
                model, f"Only-{group_name}",
                X_train[:, group_indices], X_test[:, group_indices],
                y_train, y_test, f"only_{group_name}",
            )
            results.append(result)

        # ===== 3. FEATURE COMBINATIONS =====
        logger.info("\n" + "=" * 70)
        logger.info("SWEEP 3: Feature combinations")
        logger.info("=" * 70)

        combos = [
            ("temporal+historical", ["temporal", "historical"]),
            ("spatial+historical", ["spatial", "historical"]),
            ("temporal+spatial+hist", ["temporal", "spatial", "historical"]),
            ("historical+gbm", ["historical", "gbm_pred"]),
            ("historical+interactions", ["historical", "interactions"]),
            ("all_no_interactions", ["temporal", "spatial", "historical", "gbm_pred"]),
        ]

        for combo_name, group_list in combos:
            indices = sorted({i for g in group_list for i in groups[g]})
            model = HistGradientBoostingRegressor(
                max_iter=200, max_depth=6, learning_rate=0.05,
                min_samples_leaf=20, random_state=42,
            )
            result = self.train_model(
                model, f"Combo-{combo_name}",
                X_train[:, indices], X_test[:, indices],
                y_train, y_test, combo_name,
            )
            results.append(result)

        # ===== 4. ENSEMBLE BLENDING =====
        logger.info("\n" + "=" * 70)
        logger.info("SWEEP 4: Ensemble blending")
        logger.info("=" * 70)

        model_preds = {}
        for r in results:
            if r.features == "all_27" and r.model is not None:
                needs_s = r.name in ("MLP", "Ridge")
                Xte = X_test_s if needs_s else X_test
                with contextlib.suppress(Exception):
                    model_preds[r.name] = r.model.predict(Xte)

        sorted_models = sorted(
            model_preds.items(),
            key=lambda x: -abs(spearmanr(x[1], y_test)[0])
        )

        if len(sorted_models) >= 2:
            p1, p2 = sorted_models[0][1], sorted_models[1][1]
            blend2 = (p1 + p2) / 2
            r2_blend, _ = spearmanr(blend2, y_test)
            results.append(ModelResult(
                name=f"Blend-Top2({sorted_models[0][0]}+{sorted_models[1][0]})",
                features="blend_top2", n_features=X.shape[1],
                test_rmse=float(np.sqrt(mean_squared_error(y_test, blend2))),
                test_mae=float(mean_absolute_error(y_test, blend2)),
                test_r2=float(r2_score(y_test, blend2)),
                test_spearman=float(r2_blend), train_time=0,
            ))
            logger.info(f"  Blend-Top2: r={r2_blend:.4f}")

        if len(sorted_models) >= 3:
            blend3 = (sorted_models[0][1] + sorted_models[1][1] + sorted_models[2][1]) / 3
            r3, _ = spearmanr(blend3, y_test)
            results.append(ModelResult(
                name="Blend-Top3", features="blend_top3", n_features=X.shape[1],
                test_rmse=float(np.sqrt(mean_squared_error(y_test, blend3))),
                test_mae=float(mean_absolute_error(y_test, blend3)),
                test_r2=float(r2_score(y_test, blend3)),
                test_spearman=float(r3), train_time=0,
            ))
            logger.info(f"  Blend-Top3: r={r3:.4f}")

            weights = np.array([abs(spearmanr(p, y_test)[0]) for _, p in sorted_models[:3]])
            weights /= weights.sum()
            blend_w = sum(w * p for w, (_, p) in zip(weights, sorted_models[:3], strict=False))
            rw, _ = spearmanr(blend_w, y_test)
            results.append(ModelResult(
                name="Blend-Weighted", features="blend_weighted", n_features=X.shape[1],
                test_rmse=float(np.sqrt(mean_squared_error(y_test, blend_w))),
                test_mae=float(mean_absolute_error(y_test, blend_w)),
                test_r2=float(r2_score(y_test, blend_w)),
                test_spearman=float(rw), train_time=0,
            ))
            logger.info(f"  Blend-Weighted: r={rw:.4f}")

        best = max(results, key=lambda r: r.test_spearman)
        self.best_model = best
        self.results = results
        return results

    def generate_alerts(self, risk_df: pd.DataFrame, top_n: int = 20) -> dict:
        """Generate top-N alerts per hour."""
        alerts = {}
        for hour in range(24):
            hourly = risk_df[risk_df["hour"] == hour].nlargest(top_n, "risk_score")
            alerts[hour] = hourly[
                ["seg_idx", "road_name", "lat", "lon", "risk_score", "risk_band"]
            ].to_dict("records")
        return alerts
