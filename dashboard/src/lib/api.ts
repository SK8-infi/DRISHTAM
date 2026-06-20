const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/* ── Overview ──────────────────────────────────────────── */

export interface TopRoad {
  name: string;
  total_pis: number;
}

export interface EnforcementGap {
  hours: number[];
  violations_in_gap: number;
  pct_of_total: number;
}

export interface Overview {
  total_violations: number;
  total_segments: number;
  affected_segments: number;
  total_impact: number;
  baseline_impact: number;
  estimated_cost_crore_per_day: number;
  top_roads: TopRoad[];
  hourly_distribution: Record<number, number>;
  enforcement_gap: EnforcementGap;
  unique_roads: number;
  pct_car: number;
}

export function fetchOverview(): Promise<Overview> {
  return apiFetch<Overview>("/api/overview");
}

/* ── Segments ──────────────────────────────────────────── */

export interface SegmentLight {
  seg_idx: number;
  lat: number;
  lon: number;
  lat_u: number;
  lon_u: number;
  lat_v: number;
  lon_v: number;
  road_name: string;
  highway: string;
  tier: number;
  lanes: number;
  impact_gbm: number;
  violation_count: number;
}

export interface SegmentsResponse {
  count: number;
  bbox: Record<string, number>;
  segments: SegmentLight[];
}

export interface PISBreakdown {
  capacity: number;
  importance: number;
  junction: number;
  temporal: number;
  density: number;
  severity: number;
  overall: number;
}

export interface NeighborSegment {
  seg_idx: number;
  lat: number;
  lon: number;
  impact_gbm: number;
  highway: string;
}

export interface SegmentDetail {
  seg_idx: number;
  lat: number;
  lon: number;
  lat_u: number;
  lon_u: number;
  lat_v: number;
  lon_v: number;
  road_name: string;
  highway: string;
  lanes: number;
  length_m: number;
  tier: number;
  betweenness: number;
  violation_count: number;
  impact_gbm: number;
  impact_mlp: number;
  impact_ensemble: number;
  hourly_profile: Record<number, number>;
  neighbors: NeighborSegment[];
  pis_breakdown: PISBreakdown | null;
}

export function fetchSegments(args: {
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
  min_impact?: number;
  max_impact?: number;
  tier?: number;
  limit?: number;
}): Promise<SegmentsResponse> {
  const params = new URLSearchParams({
    lat_min: args.lat_min.toString(),
    lat_max: args.lat_max.toString(),
    lon_min: args.lon_min.toString(),
    lon_max: args.lon_max.toString(),
  });
  if (args.min_impact !== undefined) params.set("min_impact", args.min_impact.toString());
  if (args.max_impact !== undefined) params.set("max_impact", args.max_impact.toString());
  if (args.tier !== undefined) params.set("tier", args.tier.toString());
  if (args.limit !== undefined) params.set("limit", args.limit.toString());
  return apiFetch<SegmentsResponse>(`/api/segments?${params}`);
}

export function fetchSegmentDetail(segIdx: number): Promise<SegmentDetail> {
  return apiFetch<SegmentDetail>(`/api/segment/${segIdx}`);
}

/* ── What-If ───────────────────────────────────────────── */

export interface ImprovedSegment {
  seg_idx: number;
  road_name: string;
  lat: number;
  lon: number;
  lat_u: number;
  lon_u: number;
  lat_v: number;
  lon_v: number;
  baseline: number;
  new: number;
  improvement: number;
}

export interface PropagationRing {
  hop: number;
  segments: number;
  total_improvement: number;
  items: ImprovedSegment[];
}

export interface CostBenefit {
  officers_needed: number;
  cost_per_day_lakhs: number;
  congestion_saved_crore: number;
  roi_multiplier: number;
}

export interface WhatIfResult {
  road_names: string[];
  segments_affected: number;
  violations_removed: number;
  baseline_impact: number;
  new_impact: number;
  impact_reduction: number;
  pct_reduction: number;
  segments_improved: number;
  top_improved: ImprovedSegment[];
  propagation: PropagationRing[];
  cost_benefit: CostBenefit | null;
}

export function runWhatIf(roadNames: string[], segIndices?: number[]): Promise<WhatIfResult> {
  const body: any = { road_names: roadNames, action: "enforce" };
  if (segIndices && segIndices.length > 0) {
    body.seg_indices = segIndices;
  }
  return apiFetch<WhatIfResult>("/api/whatif", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchWhatIfRoads(q = ""): Promise<{ roads: string[] }> {
  return apiFetch<{ roads: string[] }>(`/api/whatif/roads?q=${encodeURIComponent(q)}&limit=20`);
}

export function fetchPredefinedScenarios(): Promise<any> {
  return apiFetch<any>("/api/whatif/scenarios");
}

/* ── Risk ──────────────────────────────────────────────── */

export interface RiskSegment {
  seg_idx: number;
  road_name: string;
  lat: number;
  lon: number;
  hour: number;
  risk_score: number;
  risk_band: string;
}

export interface RiskResponse {
  hour: number;
  count: number;
  segments: RiskSegment[];
}

export function fetchRisk(hour: number, topN = 50): Promise<RiskResponse> {
  return apiFetch<RiskResponse>(`/api/risk?hour=${hour}&top_n=${topN}`);
}

export function fetchRiskAnimation(
  hourStart = 0,
  hourEnd = 23,
  topN = 30
): Promise<{ hourly_data: Record<number, RiskSegment[]> }> {
  return apiFetch(`/api/risk/animation?hour_start=${hourStart}&hour_end=${hourEnd}&top_n=${topN}`);
}

/* ── Optimizer ─────────────────────────────────────────── */

export function runOptimize(
  nOfficers = 50,
  shifts = 3,
  hoursPerShift = 2
): Promise<any> {
  return apiFetch("/api/optimize", {
    method: "POST",
    body: JSON.stringify({
      n_officers: nOfficers,
      shifts,
      hours_per_shift: hoursPerShift,
    }),
  });
}

// Removed duplicate runStationOptimize

/* ── Clusters ──────────────────────────────────────────── */

export interface ClusterSummary {
  cluster_id: number;
  n_violations: number;
  mean_pis: number;
  total_pis: number;
  mean_lat: number;
  mean_lon: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  radius_m: number;
  top_road: string;
}

export interface ClusterRoadBreakdown {
  road_name: string;
  violations: number;
  mean_pis: number;
  total_pis: number;
}

export interface ClusterDetail {
  cluster_id: number;
  n_violations: number;
  mean_pis: number;
  total_pis: number;
  mean_lat: number;
  mean_lon: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  radius_m: number;
  top_road: string;
  road_breakdown: ClusterRoadBreakdown[];
  hourly_profile: Record<number, number>;
  road_names: string[];
  vehicle_types: Record<string, number>;
  mean_severity: number;
  mean_capacity_blocked: number;
}

export function fetchClusters(topN = 30): Promise<{ count: number; clusters: ClusterSummary[] }> {
  return apiFetch(`/api/clusters?top_n=${topN}`);
}

export function fetchClusterDetail(clusterId: number): Promise<ClusterDetail> {
  return apiFetch(`/api/cluster/${clusterId}`);
}

/* ── Insights ──────────────────────────────────────────── */

export interface Insight {
  id: string;
  category: string;
  title: string;
  value: string;
  detail: string;
  source: string;
  severity: string;
  link_page: string;
  link_params: string;
}

export interface DataQuality {
  total_records: number;
  date_range: string;
  road_coverage_pct: number;
  segments_total: number;
  segments_with_violations: number;
  features_count: number;
  missing_road_names_pct: number;
  vehicle_types: number;
  hours_covered: number;
}

export interface Experiment {
  name: string;
  model_type: string;
  features: number;
  metric: string;
  score: number;
  rank: number;
}

export interface InsightsResponse {
  findings: Insight[];
  data_quality: DataQuality;
  experiments: Experiment[];
  methodology: Record<string, string>;
}

export function fetchInsights(): Promise<InsightsResponse> {
  return apiFetch("/api/insights");
}

/* ── Stations & Divisions ──────────────────────────────── */

export interface StationSummary {
  station_name: string;
  division: string;
  violations: number;
  total_pis: number;
  mean_pis: number;
  roads: number;
  devices: number;
  lat: number;
  lon: number;
  bbox: number[];
}

export interface StationDetail extends StationSummary {
  top_roads: Array<{ road_name: string; violations: number; mean_pis: number }>;
  hourly_profile: Record<string, number>;
  vehicle_types: Record<string, number>;
}

export function fetchStations(division?: string): Promise<StationSummary[]> {
  const url = division ? `/api/stations?division=${encodeURIComponent(division)}` : `/api/stations`;
  return apiFetch<StationSummary[]>(url);
}

export function fetchStationDetail(stationName: string): Promise<StationDetail> {
  return apiFetch<StationDetail>(`/api/station/${encodeURIComponent(stationName)}`);
}

export interface StationOptimizeRequest {
  n_officers?: number;
  shifts?: number;
  hours_per_shift?: number;
  station?: string;
  division?: string;
  proportional?: boolean;
  custom_allocation?: Record<string, number>;
}

export function runStationOptimize(req: StationOptimizeRequest): Promise<any> {
  return apiFetch("/api/optimize/station", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/* ── Violations ────────────────────────────────────────── */

export function fetchViolations(
  roadName?: string,
  hour?: number,
  limit = 50
): Promise<{ count: number; violations: any[] }> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (roadName) params.set("road_name", roadName);
  if (hour !== undefined) params.set("hour", hour.toString());
  return apiFetch(`/api/violations?${params}`);
}
