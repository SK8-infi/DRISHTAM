"""Tests for all API router endpoints.

Covers: overview, segments, whatif, risk, optimizer, clusters,
violations, insights, stations.
"""



# ── Overview ──────────────────────────────────────────────────


class TestOverview:
    def test_get_overview(self, client):
        r = client.get("/api/overview")
        assert r.status_code == 200
        data = r.json()
        assert "total_violations" in data
        assert "total_segments" in data
        assert "affected_segments" in data
        assert "total_impact" in data
        assert "top_roads" in data
        assert "hourly_distribution" in data
        assert "enforcement_gap" in data
        assert isinstance(data["top_roads"], list)

    def test_overview_types(self, client):
        data = client.get("/api/overview").json()
        assert isinstance(data["total_violations"], int)
        assert isinstance(data["total_segments"], int)
        assert isinstance(data["total_impact"], float)
        assert isinstance(data["pct_car"], float)


# ── Segments ──────────────────────────────────────────────────


class TestSegments:
    def test_get_segments_default_bbox(self, client):
        r = client.get("/api/segments")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "bbox" in data
        assert "segments" in data

    def test_get_segments_with_filters(self, client):
        r = client.get("/api/segments?lat_min=12.9&lat_max=13.1&lon_min=77.5&lon_max=77.7&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] <= 10

    def test_get_segments_with_impact_filter(self, client):
        r = client.get("/api/segments?min_impact=0.5&max_impact=1.0")
        assert r.status_code == 200

    def test_get_segments_with_tier_filter(self, client):
        r = client.get("/api/segments?tier=2")
        assert r.status_code == 200

    def test_get_segment_detail_found(self, client):
        r = client.get("/api/segment/0")
        assert r.status_code == 200
        data = r.json()
        assert "seg_idx" in data
        assert "road_name" in data
        assert "hourly_profile" in data
        assert "neighbors" in data

    def test_get_segment_detail_not_found(self, client):
        r = client.get("/api/segment/999999")
        assert r.status_code == 404

    def test_segment_detail_has_pis_breakdown(self, client):
        r = client.get("/api/segment/0")
        data = r.json()
        # pis_breakdown can be null or an object
        assert "pis_breakdown" in data

    def test_segments_limit_validation(self, client):
        r = client.get("/api/segments?limit=0")
        assert r.status_code == 422

    def test_segments_limit_max_validation(self, client):
        r = client.get("/api/segments?limit=99999")
        assert r.status_code == 422


# ── What-If ───────────────────────────────────────────────────


class TestWhatIf:
    def test_whatif_by_road_name(self, client):
        r = client.post("/api/whatif", json={"road_names": ["Road_0"], "action": "enforce"})
        assert r.status_code == 200
        data = r.json()
        assert "road_names" in data
        assert "segments_affected" in data

    def test_whatif_empty_roads(self, client):
        r = client.post("/api/whatif", json={"road_names": [], "action": "enforce"})
        assert r.status_code == 200
        data = r.json()
        assert data["segments_affected"] == 0

    def test_whatif_nonexistent_road(self, client):
        r = client.post("/api/whatif", json={"road_names": ["NonExistent_Road_XYZ"]})
        assert r.status_code == 200
        data = r.json()
        assert data["segments_affected"] == 0

    def test_whatif_invalid_action(self, client):
        r = client.post("/api/whatif", json={"road_names": ["Road_0"], "action": "DROP TABLE"})
        assert r.status_code == 422

    def test_whatif_too_many_roads(self, client):
        roads = [f"Road_{i}" for i in range(60)]
        r = client.post("/api/whatif", json={"road_names": roads})
        assert r.status_code == 422

    def test_whatif_scenarios(self, client):
        r = client.get("/api/whatif/scenarios")
        assert r.status_code == 200

    def test_whatif_roads_search(self, client):
        r = client.get("/api/whatif/roads?q=Road")
        assert r.status_code == 200
        data = r.json()
        assert "roads" in data

    def test_whatif_roads_search_empty(self, client):
        r = client.get("/api/whatif/roads")
        assert r.status_code == 200
        data = r.json()
        assert "roads" in data
        assert len(data["roads"]) <= 20


# ── Risk ──────────────────────────────────────────────────────


class TestRisk:
    def test_get_risk_default(self, client):
        r = client.get("/api/risk?hour=9")
        assert r.status_code == 200
        data = r.json()
        assert "hour" in data
        assert "count" in data
        assert "segments" in data
        assert data["hour"] == 9

    def test_get_risk_with_top_n(self, client):
        r = client.get("/api/risk?hour=12&top_n=5")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] <= 5

    def test_risk_invalid_hour(self, client):
        r = client.get("/api/risk?hour=25")
        assert r.status_code == 422

    def test_risk_invalid_hour_negative(self, client):
        r = client.get("/api/risk?hour=-1")
        assert r.status_code == 422

    def test_risk_animation(self, client):
        r = client.get("/api/risk/animation?hour_start=8&hour_end=10&top_n=5")
        assert r.status_code == 200
        data = r.json()
        assert "hourly_data" in data

    def test_risk_animation_default(self, client):
        r = client.get("/api/risk/animation")
        assert r.status_code == 200


# ── Optimizer ─────────────────────────────────────────────────


class TestOptimizer:
    def test_optimize_default(self, client):
        r = client.post("/api/optimize", json={})
        assert r.status_code == 200
        data = r.json()
        assert "n_officers" in data

    def test_optimize_custom_params(self, client):
        r = client.post("/api/optimize", json={"n_officers": 100, "shifts": 4, "hours_per_shift": 3})
        assert r.status_code == 200

    def test_optimize_invalid_officers(self, client):
        r = client.post("/api/optimize", json={"n_officers": 0})
        assert r.status_code == 422

    def test_optimize_too_many_officers(self, client):
        r = client.post("/api/optimize", json={"n_officers": 999})
        assert r.status_code == 422


# ── Clusters ──────────────────────────────────────────────────


class TestClusters:
    def test_get_clusters(self, client):
        r = client.get("/api/clusters")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "clusters" in data

    def test_get_clusters_with_top_n(self, client):
        r = client.get("/api/clusters?top_n=3")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] <= 3

    def test_cluster_detail_found(self, client, mock_engines):
        # Get a valid cluster_id from the mock data
        if len(mock_engines.clusters) > 0:
            cid = int(mock_engines.clusters.iloc[0]["cluster_id"])
            r = client.get(f"/api/cluster/{cid}")
            assert r.status_code == 200
            data = r.json()
            assert "cluster_id" in data
            assert "road_breakdown" in data

    def test_cluster_detail_not_found(self, client):
        r = client.get("/api/cluster/99999")
        assert r.status_code == 404

    def test_cluster_violations(self, client, mock_engines):
        if len(mock_engines.clusters) > 0:
            cid = int(mock_engines.clusters.iloc[0]["cluster_id"])
            r = client.get(f"/api/clusters/{cid}/violations?limit=5")
            assert r.status_code == 200
            data = r.json()
            assert "violations" in data


# ── Violations ────────────────────────────────────────────────


class TestViolations:
    def test_search_violations_default(self, client):
        r = client.get("/api/violations")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "violations" in data

    def test_search_violations_by_road(self, client):
        r = client.get("/api/violations?road_name=Road_0")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 0

    def test_search_violations_by_hour(self, client):
        r = client.get("/api/violations?hour=12")
        assert r.status_code == 200

    def test_search_violations_with_limit(self, client):
        r = client.get("/api/violations?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] <= 5

    def test_violations_long_road_name_rejected(self, client):
        long_name = "A" * 300
        r = client.get(f"/api/violations?road_name={long_name}")
        assert r.status_code == 422

    def test_violations_invalid_hour(self, client):
        r = client.get("/api/violations?hour=25")
        assert r.status_code == 422

    def test_violations_invalid_limit(self, client):
        r = client.get("/api/violations?limit=999")
        assert r.status_code == 422


# ── Insights ──────────────────────────────────────────────────


class TestInsights:
    def test_get_insights(self, client, mock_engines):
        # compute_insights is a complex method — patch it to return a valid structure
        from unittest.mock import patch

        mock_response = {
            "findings": [
                {
                    "id": "test",
                    "category": "impact",
                    "title": "Test",
                    "value": "1",
                    "detail": "detail",
                    "source": "test",
                    "severity": "info",
                    "link_page": "",
                    "link_params": "",
                }
            ],
            "data_quality": {
                "total_records": 200,
                "date_range": "Jan-May 2025",
                "road_coverage_pct": 50.0,
                "segments_total": 100,
                "segments_with_violations": 50,
                "features_count": 36,
                "missing_road_names_pct": 0.0,
                "vehicle_types": 4,
                "hours_covered": 24,
            },
            "experiments": [],
            "methodology": {"data": "test"},
        }
        with patch.object(mock_engines, "compute_insights", return_value=mock_response):
            r = client.get("/api/insights")
            assert r.status_code == 200
            data = r.json()
            assert "findings" in data
            assert "data_quality" in data
            assert "experiments" in data
            assert "methodology" in data


# ── Stations ──────────────────────────────────────────────────


class TestStations:
    def test_list_stations(self, client):
        r = client.get("/api/stations")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "station_name" in data[0]
            assert "division" in data[0]

    def test_list_stations_by_division(self, client):
        r = client.get("/api/stations?division=East")
        assert r.status_code == 200

    def test_station_detail_found(self, client, mock_engines):
        if len(mock_engines.stations) > 0:
            name = mock_engines.stations.iloc[0]["station_name"]
            r = client.get(f"/api/station/{name}")
            assert r.status_code == 200
            data = r.json()
            assert "station_name" in data
            assert "hourly_profile" in data

    def test_station_detail_not_found(self, client):
        r = client.get("/api/station/NonExistent_Station")
        assert r.status_code == 404

    def test_station_optimize(self, client):
        r = client.post("/api/optimize/station", json={"n_officers": 10, "shifts": 2})
        assert r.status_code == 200

    def test_station_optimize_by_division(self, client):
        r = client.post("/api/optimize/station", json={"division": "East", "n_officers": 10})
        assert r.status_code == 200

    def test_station_optimize_invalid_division(self, client):
        r = client.post("/api/optimize/station", json={"division": "InvalidDiv"})
        assert r.status_code == 422

    def test_station_optimize_custom_allocation(self, client):
        r = client.post(
            "/api/optimize/station",
            json={
                "custom_allocation": {"Cubbon Park": 5, "Halasuru Gate": 3},
                "n_officers": 8,
            },
        )
        assert r.status_code == 200

    def test_station_optimize_with_spacing(self, client):
        """Test optimization with custom officer spacing."""
        r = client.post(
            "/api/optimize/station",
            json={"n_officers": 10, "min_officer_spacing_m": 750.0},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["min_officer_spacing_m"] == 750.0

    def test_station_optimize_spacing_zero(self, client):
        """Setting spacing to 0 disables the constraint."""
        r = client.post(
            "/api/optimize/station",
            json={"n_officers": 5, "min_officer_spacing_m": 0},
        )
        assert r.status_code == 200

    def test_station_optimize_spacing_too_large(self, client):
        """Spacing > 5000m should be rejected by validation."""
        r = client.post(
            "/api/optimize/station",
            json={"n_officers": 5, "min_officer_spacing_m": 10000},
        )
        assert r.status_code == 422

    def test_station_optimize_spacing_negative(self, client):
        """Negative spacing should be rejected by validation."""
        r = client.post(
            "/api/optimize/station",
            json={"n_officers": 5, "min_officer_spacing_m": -100},
        )
        assert r.status_code == 422

    def test_optimize_default_includes_spacing(self, client):
        """Global optimize endpoint also supports spacing param."""
        r = client.post("/api/optimize", json={"min_officer_spacing_m": 500})
        assert r.status_code == 200
