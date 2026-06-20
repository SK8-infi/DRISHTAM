"""DRISHTAM API — Pydantic response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Shared ────────────────────────────────────────────────────

class Coords(BaseModel):
    lat: float
    lon: float


# ── Overview ──────────────────────────────────────────────────

class TopRoad(BaseModel):
    name: str
    total_pis: float


class EnforcementGap(BaseModel):
    hours: list[int]
    violations_in_gap: int
    pct_of_total: float


class OverviewResponse(BaseModel):
    total_violations: int
    total_segments: int
    affected_segments: int
    total_impact: float
    baseline_impact: float
    estimated_cost_crore_per_day: float
    top_roads: list[TopRoad]
    hourly_distribution: dict[int, int]
    enforcement_gap: EnforcementGap
    unique_roads: int
    pct_car: float


# ── Segments ──────────────────────────────────────────────────

class SegmentLight(BaseModel):
    """Lightweight segment for map rendering (includes line geometry)."""
    seg_idx: int
    lat: float
    lon: float
    lat_u: float = 0.0
    lon_u: float = 0.0
    lat_v: float = 0.0
    lon_v: float = 0.0
    road_name: str = ""
    highway: str = ""
    tier: int = 0
    lanes: int = 1
    impact_gbm: float = 0.0
    violation_count: float = 0.0


class PISBreakdown(BaseModel):
    capacity: float
    importance: float
    junction: float
    temporal: float
    density: float
    severity: float
    overall: float


class NeighborSegment(BaseModel):
    seg_idx: int
    lat: float
    lon: float
    impact_gbm: float
    highway: str = ""


class SegmentDetail(BaseModel):
    """Full segment detail for microscopic inspection."""
    seg_idx: int
    osm_u: str = ""
    osm_v: str = ""
    lat: float
    lon: float
    lat_u: float = 0.0
    lon_u: float = 0.0
    lat_v: float = 0.0
    lon_v: float = 0.0
    road_name: str = ""
    highway: str = ""
    lanes: int = 1
    length_m: float = 0.0
    tier: int = 0
    betweenness: float = 0.0
    violation_count: float = 0.0
    impact_true: float = 0.0
    impact_gbm: float = 0.0
    impact_mlp: float = 0.0
    impact_ensemble: float = 0.0
    hourly_profile: dict[int, int] = {}
    neighbors: list[NeighborSegment] = []
    pis_breakdown: PISBreakdown | None = None


class SegmentsResponse(BaseModel):
    count: int
    bbox: dict[str, float]
    segments: list[SegmentLight]


# ── What-If ───────────────────────────────────────────────────

class WhatIfRequest(BaseModel):
    road_names: list[str] = []
    seg_indices: list[int] = []  # If provided, enforce only these specific segments
    action: str = "enforce"


class ImprovedSegment(BaseModel):
    seg_idx: int
    road_name: str
    lat: float
    lon: float
    lat_u: float = 0.0
    lon_u: float = 0.0
    lat_v: float = 0.0
    lon_v: float = 0.0
    baseline: float
    new: float
    improvement: float


class PropagationRing(BaseModel):
    """Segments affected at a given hop distance from enforced roads."""
    hop: int = Field(description="0 = directly enforced, 1 = 1-hop neighbor, etc.")
    segments: int
    total_improvement: float
    items: list[ImprovedSegment] = []


class CostBenefit(BaseModel):
    officers_needed: int
    cost_per_day_lakhs: float
    congestion_saved_crore: float
    roi_multiplier: float


class WhatIfResponse(BaseModel):
    road_names: list[str]
    segments_affected: int
    violations_removed: int
    baseline_impact: float = 0.0
    new_impact: float = 0.0
    impact_reduction: float = 0.0
    pct_reduction: float = 0.0
    segments_improved: int = 0
    top_improved: list[ImprovedSegment] = []
    propagation: list[PropagationRing] = []
    cost_benefit: CostBenefit | None = None


# ── Risk ──────────────────────────────────────────────────────

class RiskSegment(BaseModel):
    seg_idx: int
    road_name: str
    lat: float
    lon: float
    hour: int
    risk_score: float
    risk_band: str


class RiskResponse(BaseModel):
    hour: int
    count: int
    segments: list[RiskSegment]


# ── Optimizer ─────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    n_officers: int = Field(default=50, ge=1, le=500)
    shifts: int = Field(default=3, ge=1, le=6)
    hours_per_shift: int = Field(default=2, ge=1, le=8)


# ── Stations & Divisions ─────────────────────────────────────

class StationSummary(BaseModel):
    station_name: str
    division: str          # "East", "West", "North", "South"
    violations: int
    total_pis: float
    mean_pis: float
    roads: int
    devices: int
    lat: float             # centroid
    lon: float
    bbox: list[float] = []  # [min_lat, min_lon, max_lat, max_lon]


class StationDetail(BaseModel):
    station_name: str
    division: str
    violations: int
    total_pis: float
    mean_pis: float
    roads: int
    devices: int
    lat: float
    lon: float
    top_roads: list[dict] = []          # [{road_name, violations, mean_pis}]
    hourly_profile: dict[str, int] = {}
    vehicle_types: dict[str, int] = {}


class StationOptimizeRequest(BaseModel):
    n_officers: int = Field(default=50, ge=1, le=500)
    shifts: int = Field(default=3, ge=1, le=6)
    hours_per_shift: int = Field(default=2, ge=1, le=8)
    station: str | None = None      # optimize for a single station
    division: str | None = None     # optimize within a division
    proportional: bool = True       # distribute officers proportional to station impact
    custom_allocation: dict[str, int] | None = None  # custom mapping of station_name -> n_officers


# ── Clusters ──────────────────────────────────────────────────

class ClusterSummary(BaseModel):
    cluster_id: int
    n_violations: int
    mean_pis: float
    total_pis: float
    mean_lat: float
    mean_lon: float
    min_lat: float = 0.0
    max_lat: float = 0.0
    min_lon: float = 0.0
    max_lon: float = 0.0
    radius_m: float = 0.0
    top_road: str = ""


class ClusterRoadBreakdown(BaseModel):
    road_name: str
    violations: int
    mean_pis: float
    total_pis: float


class ClusterDetail(BaseModel):
    """Full cluster detail for drill-down panel."""
    cluster_id: int
    n_violations: int
    mean_pis: float
    total_pis: float
    mean_lat: float
    mean_lon: float
    min_lat: float = 0.0
    max_lat: float = 0.0
    min_lon: float = 0.0
    max_lon: float = 0.0
    radius_m: float = 0.0
    top_road: str = ""
    road_breakdown: list[ClusterRoadBreakdown] = []
    hourly_profile: dict[int, int] = {}
    road_names: list[str] = []
    vehicle_types: dict[str, int] = {}
    mean_severity: float = 0.0
    mean_capacity_blocked: float = 0.0


# ── Violations ────────────────────────────────────────────────

class ViolationRecord(BaseModel):
    id: int | str
    latitude: float
    longitude: float
    road_name: str = ""
    violation_type: str = ""
    vehicle_type_clean: str = ""
    hour_ist: int = 0
    pis: float = 0.0
    capacity_blocked_pct: float = 0.0
    violation_severity: float = 0.0


# ── Insights ──────────────────────────────────────────────────

class Insight(BaseModel):
    """A single data-driven insight computed from live engines."""
    id: str
    category: str  # "impact", "enforcement", "risk", "optimizer", "bias"
    title: str
    value: str  # the hero number
    detail: str
    source: str
    severity: str = "info"  # "critical", "warning", "info", "success"
    link_page: str = ""  # frontend page to link to
    link_params: str = ""  # query params


class DataQuality(BaseModel):
    total_records: int
    date_range: str
    road_coverage_pct: float
    segments_total: int
    segments_with_violations: int
    features_count: int
    missing_road_names_pct: float
    vehicle_types: int
    hours_covered: int


class Experiment(BaseModel):
    name: str
    model_type: str
    features: int
    metric: str
    score: float
    rank: int


class InsightsResponse(BaseModel):
    findings: list[Insight]
    data_quality: DataQuality
    experiments: list[Experiment]
    methodology: dict[str, str]

