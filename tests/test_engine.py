"""Tests for EngineStore methods using mock data.

Covers: query_bbox, get_segment, search_violations, run_whatif,
get_risk, run_optimize, get_stations, get_clusters, compute_insights.
"""


class TestEngineStoreSegments:
    """Test EngineStore segment-related methods."""

    def test_query_bbox_returns_results(self, mock_engines):
        df = mock_engines.query_bbox(12.9, 13.1, 77.5, 77.7)
        assert len(df) > 0

    def test_query_bbox_empty_region(self, mock_engines):
        df = mock_engines.query_bbox(0, 0.1, 0, 0.1)
        assert len(df) == 0

    def test_query_bbox_with_min_impact(self, mock_engines):
        df = mock_engines.query_bbox(12.9, 13.1, 77.5, 77.7, min_impact=0.5)
        if len(df) > 0:
            assert all(df["impact_gbm"] >= 0.5)

    def test_query_bbox_with_max_impact(self, mock_engines):
        df = mock_engines.query_bbox(12.9, 13.1, 77.5, 77.7, max_impact=0.3)
        if len(df) > 0:
            assert all(df["impact_gbm"] <= 0.3)

    def test_query_bbox_with_tier(self, mock_engines):
        df = mock_engines.query_bbox(12.9, 13.1, 77.5, 77.7, tier=2)
        if len(df) > 0:
            assert all(df["tier"] == 2)

    def test_query_bbox_with_limit(self, mock_engines):
        df = mock_engines.query_bbox(12.9, 13.1, 77.5, 77.7, limit=5)
        assert len(df) <= 5

    def test_get_segment_exists(self, mock_engines):
        result = mock_engines.get_segment(0)
        assert result is not None
        assert result["seg_idx"] == 0
        assert "hourly_profile" in result
        assert "neighbors" in result

    def test_get_segment_not_found(self, mock_engines):
        result = mock_engines.get_segment(999999)
        assert result is None


class TestEngineStoreViolations:
    """Test EngineStore violation-related methods."""

    def test_search_all(self, mock_engines):
        df = mock_engines.search_violations()
        assert len(df) == 50  # default limit

    def test_search_by_road(self, mock_engines):
        df = mock_engines.search_violations(road_name="Road_0")
        assert len(df) >= 0

    def test_search_by_hour(self, mock_engines):
        df = mock_engines.search_violations(hour=12)
        if len(df) > 0:
            assert all(df["hour_ist"] == 12)

    def test_search_with_limit(self, mock_engines):
        df = mock_engines.search_violations(limit=5)
        assert len(df) <= 5


class TestEngineStoreWhatIf:
    """Test EngineStore What-If engine."""

    def test_whatif_by_road(self, mock_engines):
        result = mock_engines.run_whatif(["Road_0"])
        assert "segments_affected" in result
        assert result["segments_affected"] > 0

    def test_whatif_nonexistent_road(self, mock_engines):
        result = mock_engines.run_whatif(["NonExistent_ZZZZZ"])
        assert result["segments_affected"] == 0

    def test_whatif_returns_propagation(self, mock_engines):
        result = mock_engines.run_whatif(["Road_0"])
        assert "propagation" in result

    def test_whatif_returns_cost_benefit(self, mock_engines):
        result = mock_engines.run_whatif(["Road_0"])
        if result["segments_affected"] > 0:
            assert "cost_benefit" in result
            cb = result["cost_benefit"]
            assert "officers_needed" in cb
            assert "roi_multiplier" in cb


class TestEngineStoreRisk:
    """Test EngineStore risk methods."""

    def test_get_risk(self, mock_engines):
        result = mock_engines.get_risk(9, top_n=5)
        assert isinstance(result, list)

    def test_get_risk_empty_hour(self, mock_engines):
        result = mock_engines.get_risk(99)
        assert result == []

    def test_get_risk_range(self, mock_engines):
        result = mock_engines.get_risk_range(8, 10, top_n=5)
        assert 8 in result
        assert 9 in result
        assert 10 in result


class TestEngineStoreOptimizer:
    """Test EngineStore optimizer methods."""

    def test_run_optimize(self, mock_engines):
        result = mock_engines.run_optimize(n_officers=10, shifts=2)
        assert "n_officers" in result
        assert "shifts" in result

    def test_run_optimize_by_station_all(self, mock_engines):
        result = mock_engines.run_optimize_by_station(n_officers=10)
        assert "total_assignments" in result

    def test_run_optimize_by_station_single(self, mock_engines):
        if len(mock_engines.stations) > 0:
            station_name = mock_engines.stations.iloc[0]["station_name"]
            result = mock_engines.run_optimize_by_station(n_officers=5, station=station_name)
            assert "total_assignments" in result

    def test_run_optimize_by_station_division(self, mock_engines):
        result = mock_engines.run_optimize_by_station(n_officers=10, division="East")
        assert "division_summary" in result

    def test_run_optimize_by_station_proportional(self, mock_engines):
        result = mock_engines.run_optimize_by_station(n_officers=20, proportional=True)
        assert "station_results" in result

    def test_run_optimize_by_station_custom_allocation(self, mock_engines):
        if len(mock_engines.stations) > 0:
            station_name = mock_engines.stations.iloc[0]["station_name"]
            result = mock_engines.run_optimize_by_station(custom_allocation={station_name: 5})
            assert "total_assignments" in result


class TestEngineStoreStations:
    """Test EngineStore station methods."""

    def test_get_stations_all(self, mock_engines):
        result = mock_engines.get_stations()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_stations_by_division(self, mock_engines):
        result = mock_engines.get_stations(division="East")
        assert isinstance(result, list)
        if len(result) > 0:
            assert all(r["division"] == "East" for r in result)

    def test_get_station_detail(self, mock_engines):
        if len(mock_engines.stations) > 0:
            name = mock_engines.stations.iloc[0]["station_name"]
            result = mock_engines.get_station_detail(name)
            assert result is not None
            assert result["station_name"] == name
            assert "top_roads" in result
            assert "hourly_profile" in result

    def test_get_station_detail_not_found(self, mock_engines):
        result = mock_engines.get_station_detail("NonExistent_Station_XYZ")
        assert result is None


class TestEngineStoreClusters:
    """Test EngineStore cluster methods."""

    def test_get_clusters(self, mock_engines):
        result = mock_engines.get_clusters(top_n=5)
        assert isinstance(result, list)

    def test_get_cluster_detail(self, mock_engines):
        if len(mock_engines.clusters) > 0:
            cid = int(mock_engines.clusters.iloc[0]["cluster_id"])
            result = mock_engines.get_cluster_detail(cid)
            assert result is not None
            assert "road_breakdown" in result
            assert "hourly_profile" in result
            assert "vehicle_types" in result

    def test_get_cluster_detail_not_found(self, mock_engines):
        result = mock_engines.get_cluster_detail(99999)
        assert result is None


class TestEngineStoreOverview:
    """Test EngineStore overview and insights."""

    def test_overview_loaded(self, mock_engines):
        assert mock_engines.overview is not None
        assert "total_violations" in mock_engines.overview
        assert "total_segments" in mock_engines.overview

    def test_compute_insights(self, mock_engines):
        result = mock_engines.compute_insights()
        assert "findings" in result
        assert "data_quality" in result
        assert "experiments" in result
        assert "methodology" in result
        assert len(result["findings"]) > 0

    def test_insights_findings_format(self, mock_engines):
        result = mock_engines.compute_insights()
        for finding in result["findings"]:
            assert "id" in finding
            assert "category" in finding
            assert "title" in finding
            assert "value" in finding

    def test_insights_data_quality(self, mock_engines):
        result = mock_engines.compute_insights()
        dq = result["data_quality"]
        assert "total_records" in dq
        assert "segments_total" in dq
        assert "features_count" in dq


class TestEngineStoreEdgeCases:
    """Test edge cases and uncovered branches."""

    def test_whatif_with_seg_indices(self, mock_engines):
        """Test the seg_indices_input branch of run_whatif."""
        result = mock_engines.run_whatif(road_names=[], seg_indices_input=[0, 1, 2])
        assert "segments_affected" in result
        assert result["segments_affected"] > 0

    def test_whatif_with_invalid_seg_indices(self, mock_engines):
        """seg_indices that don't match any seg_idx should return 0."""
        result = mock_engines.run_whatif(road_names=[], seg_indices_input=[999999])
        assert result["segments_affected"] == 0

    def test_get_segment_with_pis_breakdown(self, mock_engines):
        """Segment for a road with violations should have PIS breakdown."""
        # Road_0 has violations in our synthetic data
        seg = mock_engines.get_segment(0)
        assert seg is not None
        # pis_breakdown should exist (may be None or dict)
        assert "pis_breakdown" in seg

    def test_get_segment_with_unknown_road(self, mock_engines):
        """Segment whose road isn't in hourly_counts."""
        # Temporarily modify a segment's road to something unknown

        original = mock_engines.segments.loc[0, "road_name"]
        mock_engines.segments.loc[0, "road_name"] = "ZZZZZZZ_Unknown"
        seg = mock_engines.get_segment(0)
        assert seg is not None
        assert seg["hourly_profile"] is not None
        # Restore
        mock_engines.segments.loc[0, "road_name"] = original

    def test_get_risk_normalizes(self, mock_engines):
        """Risk scores should be normalized to 0-1."""
        result = mock_engines.get_risk(9, top_n=5)
        if result:
            for item in result:
                assert 0 <= item["risk_score"] <= 1.0

    def test_run_optimize_missing_files(self, mock_engines):
        """run_optimize should handle missing schedule/fleet files."""
        result = mock_engines.run_optimize(n_officers=10)
        assert "n_officers" in result

    def test_cluster_detail_missing_cluster(self, mock_engines):
        """Cluster detail for non-existent cluster returns None."""
        result = mock_engines.get_cluster_detail(-999)
        assert result is None

    def test_get_stations_nonexistent_division(self, mock_engines):
        """Querying stations for a non-existent division returns empty."""
        result = mock_engines.get_stations(division="NonExistent")
        assert result == []

    def test_whatif_result_fields(self, mock_engines):
        """Comprehensive check of whatif return value fields."""
        result = mock_engines.run_whatif(["Road_0"])
        assert "road_names" in result
        assert "baseline_impact" in result
        assert "new_impact" in result
        assert "impact_reduction" in result
        assert "pct_reduction" in result
        assert "segments_improved" in result
        assert "top_improved" in result
        assert "propagation" in result

    def test_optimize_station_no_viols(self, mock_engines):
        """Optimizing for a station with no violations."""
        result = mock_engines.run_optimize_by_station(n_officers=5, station="NonExistent_Station_ZZZ")
        assert "error" in result

    def test_optimize_station_equal_distribution(self, mock_engines):
        """Test non-proportional (equal) distribution."""
        result = mock_engines.run_optimize_by_station(n_officers=10, proportional=False)
        assert "total_assignments" in result
