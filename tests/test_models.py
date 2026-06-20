"""Tests for Pydantic models (api/models.py).

Covers: all request models with validation bounds, edge cases,
and field constraints.
"""

import pytest
from pydantic import ValidationError

from api.models import (
    OptimizeRequest,
    StationOptimizeRequest,
    WhatIfRequest,
)


class TestWhatIfRequest:
    def test_default_values(self):
        req = WhatIfRequest()
        assert req.road_names == []
        assert req.seg_indices == []
        assert req.action == "enforce"

    def test_valid_enforce(self):
        req = WhatIfRequest(road_names=["MG Road", "Brigade Road"], action="enforce")
        assert len(req.road_names) == 2

    def test_valid_remove(self):
        req = WhatIfRequest(road_names=["MG Road"], action="remove")
        assert req.action == "remove"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            WhatIfRequest(action="DROP TABLE")

    def test_road_names_max_length(self):
        with pytest.raises(ValidationError):
            WhatIfRequest(road_names=[f"Road_{i}" for i in range(60)])

    def test_seg_indices_max_length(self):
        with pytest.raises(ValidationError):
            WhatIfRequest(seg_indices=list(range(6000)))

    def test_road_names_sanitized(self):
        req = WhatIfRequest(road_names=["  MG Road  ", "  ", "Brigade Road"])
        assert "MG Road" in req.road_names
        assert "Brigade Road" in req.road_names
        # Empty strings stripped out
        assert "" not in req.road_names

    def test_road_names_truncated(self):
        long_name = "A" * 500
        req = WhatIfRequest(road_names=[long_name])
        assert len(req.road_names[0]) <= 200

    def test_seg_indices_valid(self):
        req = WhatIfRequest(seg_indices=[1, 2, 3, 100, 200])
        assert len(req.seg_indices) == 5


class TestOptimizeRequest:
    def test_default_values(self):
        req = OptimizeRequest()
        assert req.n_officers == 50
        assert req.shifts == 3
        assert req.hours_per_shift == 2

    def test_valid_custom(self):
        req = OptimizeRequest(n_officers=100, shifts=4, hours_per_shift=4)
        assert req.n_officers == 100

    def test_officers_too_low(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(n_officers=0)

    def test_officers_too_high(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(n_officers=999)

    def test_shifts_too_high(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(shifts=10)

    def test_hours_too_high(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(hours_per_shift=10)


class TestStationOptimizeRequest:
    def test_default_values(self):
        req = StationOptimizeRequest()
        assert req.n_officers == 50
        assert req.station is None
        assert req.division is None
        assert req.proportional is True

    def test_valid_division(self):
        req = StationOptimizeRequest(division="East")
        assert req.division == "East"

    def test_invalid_division(self):
        with pytest.raises(ValidationError):
            StationOptimizeRequest(division="InvalidDiv")

    def test_station_max_length(self):
        with pytest.raises(ValidationError):
            StationOptimizeRequest(station="A" * 200)

    def test_custom_allocation_valid(self):
        req = StationOptimizeRequest(
            custom_allocation={"Station A": 5, "Station B": 10}
        )
        assert len(req.custom_allocation) == 2

    def test_custom_allocation_too_many(self):
        alloc = {f"Station_{i}": 1 for i in range(70)}
        with pytest.raises(ValidationError):
            StationOptimizeRequest(custom_allocation=alloc)

    def test_custom_allocation_values_capped(self):
        req = StationOptimizeRequest(
            custom_allocation={"Station A": 999}
        )
        assert req.custom_allocation["Station A"] <= 500

    def test_all_valid_divisions(self):
        for div in ["East", "West", "North", "South"]:
            req = StationOptimizeRequest(division=div)
            assert req.division == div
