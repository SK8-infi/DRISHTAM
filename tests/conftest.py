"""Shared test fixtures — synthetic EngineStore with fake data.

All API tests use these fixtures to avoid loading real data files.
The mock engine provides realistic DataFrame structures matching
what engine_loader.py produces from the real data.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

# ── Synthetic Data Builders ────────────────────────────────────


def _build_segments(n: int = 100) -> pd.DataFrame:
    """Build a realistic segments DataFrame."""
    rng = np.random.RandomState(42)
    return pd.DataFrame(
        {
            "seg_idx": np.arange(n),
            "lat": 12.9 + rng.rand(n) * 0.2,
            "lon": 77.5 + rng.rand(n) * 0.2,
            "lat_u": 12.9 + rng.rand(n) * 0.2,
            "lon_u": 77.5 + rng.rand(n) * 0.2,
            "lat_v": 12.9 + rng.rand(n) * 0.2,
            "lon_v": 77.5 + rng.rand(n) * 0.2,
            "road_name": [f"Road_{i % 10}" for i in range(n)],
            "highway": rng.choice(["tertiary", "secondary", "primary", "trunk"], n),
            "tier": rng.randint(0, 5, n),
            "lanes": rng.randint(1, 4, n),
            "length_m": rng.rand(n) * 1000,
            "betweenness": rng.rand(n),
            "impact_gbm": rng.rand(n),
            "impact_mlp": rng.rand(n),
            "impact_ensemble": rng.rand(n),
            "impact_true": rng.rand(n),
            "violation_count": rng.randint(0, 50, n).astype(float),
            "osm_u": [f"u_{i}" for i in range(n)],
            "osm_v": [f"v_{i}" for i in range(n)],
        }
    )


def _build_violations(n: int = 200) -> pd.DataFrame:
    """Build a realistic violations DataFrame."""
    rng = np.random.RandomState(42)
    return pd.DataFrame(
        {
            "id": np.arange(n),
            "latitude": 12.9 + rng.rand(n) * 0.2,
            "longitude": 77.5 + rng.rand(n) * 0.2,
            "road_name": [f"Road_{i % 10}" for i in range(n)],
            "violation_type": rng.choice(["No Parking", "Double Parking", "Wrong Side"], n),
            "vehicle_type": rng.choice(["Car", "Bike", "Auto", "Bus"], n),
            "vehicle_type_clean": rng.choice(["CAR", "BIKE", "AUTO", "BUS"], n),
            "hour_ist": rng.randint(0, 24, n),
            "pis": rng.rand(n) * 100,
            "pis_capacity": rng.rand(n) * 20,
            "pis_importance": rng.rand(n) * 20,
            "pis_junction": rng.rand(n) * 10,
            "pis_temporal": rng.rand(n) * 20,
            "pis_density": rng.rand(n) * 15,
            "pis_severity": rng.rand(n) * 15,
            "capacity_blocked_pct": rng.rand(n) * 100,
            "violation_severity": rng.rand(n) * 10,
            "cluster_id": rng.randint(-1, 5, n),
            "police_station": rng.choice(
                ["Cubbon Park", "Halasuru Gate", "Upparpet", "Kodigehalli", "J.P. Nagar"],
                n,
            ),
            "device_id": rng.choice(["D001", "D002", "D003", "D004"], n),
        }
    )


def _build_risk(n: int = 50) -> pd.DataFrame:
    """Build a realistic risk predictions DataFrame."""
    rng = np.random.RandomState(42)
    rows = []
    for hour in range(24):
        for _ in range(n):
            rows.append(
                {
                    "seg_idx": rng.randint(0, 100),
                    "road_name": f"Road_{rng.randint(0, 10)}",
                    "lat": 12.9 + rng.rand() * 0.2,
                    "lon": 77.5 + rng.rand() * 0.2,
                    "hour": hour,
                    "risk_score": rng.rand() * 100,
                    "risk_band": rng.choice(["high", "medium", "low"]),
                }
            )
    return pd.DataFrame(rows)


from api.engine_loader import EngineStore


class MockEngineStore(EngineStore):
    """Functional mock that inherits all business methods from EngineStore.

    Only load_all() is overridden to use synthetic data.
    """

    def __init__(self):
        self.ready = False

    def load_all(self):
        """Load synthetic data into all engine attributes."""
        self.segments = _build_segments(100)
        self.violations = _build_violations(200)
        self.risk_df = _build_risk(10)

        # Spatial index arrays
        self.seg_lat = self.segments["lat"].values
        self.seg_lon = self.segments["lon"].values
        self.seg_impact = self.segments["impact_gbm"].values

        # Hourly counts
        self.hourly_counts = self.violations.groupby(["road_name", "hour_ist"]).size().unstack(fill_value=0)
        self.total_violations = len(self.violations)

        # Road to station mapping
        road_station = (
            self.violations.groupby(["road_name", "police_station"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .drop_duplicates(subset="road_name", keep="first")
        )
        self.road_to_station = dict(zip(road_station["road_name"], road_station["police_station"], strict=False))

        # Mock ML models
        self.gbm = MagicMock()
        self.gbm.predict = MagicMock(return_value=np.random.rand(100))
        self.scaler = MagicMock()
        self.scaler.transform = MagicMock(return_value=np.random.rand(100, 36))
        self.features = np.random.rand(100, 36)
        self.baseline_preds = np.random.rand(100)
        self.baseline_impact = float(self.baseline_preds.sum())

        # Scenarios
        self.scenarios = {"scenarios": [], "metadata": {}}

        # Road stats
        self.road_stats = (
            self.violations.groupby("road_name")
            .agg(total_violations=("id", "count"), mean_pis=("pis", "mean"), max_pis=("pis", "max"))
            .reset_index()
        )

        # Stations
        self._load_mock_stations()

        # Clusters
        self._load_mock_clusters()

        # Overview
        self._compute_mock_overview()

        self.ready = True
        # Cache attributes (matching EngineStore.load_all)
        self._insights_cache: dict | None = None
        self._risk_cache: dict = {}
        self._clusters_cache: list | None = None
        self._stations_cache: dict = {}

    def _load_mock_stations(self):
        from api.engine_loader import STATION_TO_DIVISION

        valid = self.violations[
            self.violations["police_station"].notna() & (self.violations["police_station"] != "No Police Station")
        ]
        stations = (
            valid.groupby("police_station")
            .agg(
                violations=("id", "count"),
                mean_pis=("pis", "mean"),
                total_pis=("pis", "sum"),
                mean_lat=("latitude", "mean"),
                mean_lon=("longitude", "mean"),
                min_lat=("latitude", "min"),
                max_lat=("latitude", "max"),
                min_lon=("longitude", "min"),
                max_lon=("longitude", "max"),
                roads=("road_name", "nunique"),
                devices=("device_id", "nunique"),
            )
            .reset_index()
            .rename(columns={"police_station": "station_name"})
        )
        stations["division"] = stations["station_name"].map(lambda s: STATION_TO_DIVISION.get(s, "Unassigned"))
        stations["bbox"] = stations.apply(lambda r: [r["min_lat"], r["min_lon"], r["max_lat"], r["max_lon"]], axis=1)
        self.stations = stations.sort_values("violations", ascending=False)

    def _load_mock_clusters(self):
        clustered = self.violations[self.violations["cluster_id"] >= 0]
        if len(clustered) > 0:
            clusters = (
                clustered.groupby("cluster_id")
                .agg(
                    n_violations=("id", "count"),
                    mean_pis=("pis", "mean"),
                    total_pis=("pis", "sum"),
                    mean_lat=("latitude", "mean"),
                    mean_lon=("longitude", "mean"),
                    min_lat=("latitude", "min"),
                    max_lat=("latitude", "max"),
                    min_lon=("longitude", "min"),
                    max_lon=("longitude", "max"),
                    top_road=("road_name", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else ""),
                )
                .reset_index()
            )
            clusters["radius_m"] = (
                ((clusters["max_lat"] - clusters["min_lat"]) ** 2 + (clusters["max_lon"] - clusters["min_lon"]) ** 2)
                ** 0.5
                * 111_000
                / 2
            )
            self.clusters = clusters.sort_values("total_pis", ascending=False)
        else:
            self.clusters = pd.DataFrame()

    def _compute_mock_overview(self):
        v = self.violations
        s = self.segments
        affected = int((s["impact_gbm"] > 0.01).sum())
        total_impact = float(s["impact_gbm"].sum())
        top_roads = v[v["road_name"] != "Unnamed"].groupby("road_name")["pis"].sum().nlargest(10)
        hourly = v.groupby("hour_ist").size().to_dict()
        gap_hours = list(range(15, 21))
        gap_violations = int(v[v["hour_ist"].isin(gap_hours)].shape[0])

        self.overview = {
            "total_violations": self.total_violations,
            "total_segments": len(s),
            "affected_segments": affected,
            "total_impact": round(total_impact, 1),
            "baseline_impact": round(self.baseline_impact, 1),
            "estimated_cost_crore_per_day": round(total_impact * 0.0015, 1),
            "top_roads": [{"name": name, "total_pis": round(float(pis), 1)} for name, pis in top_roads.items()],
            "hourly_distribution": {int(k): int(v_) for k, v_ in hourly.items()},
            "enforcement_gap": {
                "hours": gap_hours,
                "violations_in_gap": gap_violations,
                "pct_of_total": round(100 * gap_violations / max(self.total_violations, 1), 1),
            },
            "unique_roads": int(v["road_name"].nunique()),
            "pct_car": round(100 * (v["vehicle_type_clean"] == "CAR").mean(), 1),
        }


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture(scope="session")
def mock_engines():
    """Create a mock engine store loaded with synthetic data."""
    store = MockEngineStore()
    store.load_all()
    return store


@pytest.fixture(scope="session")
def client(mock_engines):
    """Create a FastAPI test client with mocked engines."""
    # Patch engines at the module level before importing app
    with patch("api.engine_loader.ensure_data_downloaded", return_value=(Path("/tmp/data"), Path("/tmp/models"))):
        with patch("api.engine_loader.engines", mock_engines):
            # Also patch all router references
            with (
                patch("api.routers.overview.engines", mock_engines),
                patch("api.routers.segments.engines", mock_engines),
                patch("api.routers.whatif.engines", mock_engines),
                patch("api.routers.risk.engines", mock_engines),
                patch("api.routers.optimizer.engines", mock_engines),
                patch("api.routers.clusters.engines", mock_engines),
                patch("api.routers.violations.engines", mock_engines),
                patch("api.routers.insights.engines", mock_engines),
                patch("api.routers.stations.engines", mock_engines),
            ):
                from api.main import app

                yield TestClient(app)
