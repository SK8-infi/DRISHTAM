# Phase 1: Data Foundation & Enrichment Pipeline ✅ COMPLETE

> **Goal**: Build the rock-solid data layer that everything depends on.  
> **Inputs**: Raw CSVs + OSM GraphML  
> **Outputs**: `violations_enriched.parquet` with 77 features per violation  
> **Status**: ✅ COMPLETE — committed `4fdc5fb` on 2026-06-17  
> **Runtime**: 536.6s on GCP VM (e2-standard-4, 16GB RAM, Mumbai)

---

## 1.1 Data Loading & Cleaning Module

### Step 1.1.1: Violation Data Loader

```
File: drishtam/data_pipeline.py → load_violations()
```

**Tasks**:
- [x] Load `jan to may police violation_anonymized791b166.csv` (298K records)
- [x] Parse `created_datetime` → pd.Timestamp (UTC-aware)
- [x] Drop NaT rows (only ~5)
- [x] Filter to Bengaluru bbox: lat ∈ [12.7, 13.4], lon ∈ [77.3, 77.9]
- [x] Parse `violation_type` — split multi-violation records (JSON array + comma-separated)
- [x] Create `is_congestion_relevant` flag for: PARKING IN A MAIN ROAD, DOUBLE PARKING, PARKING NEAR ROAD CROSSING, PARKING NEAR BUSTOP/SCHOOL/HOSPITAL
- [x] Create IST datetime column: `created_datetime_ist = created_datetime + 5:30`
- [x] Extract temporal features: `hour_ist`, `day_of_week`, `month`, `is_weekend`, `is_peak_morning` (8-10 AM), `is_peak_evening` (5-8 PM)
- [x] Parse `vehicle_type` → map to `vehicle_width_m` using lookup table
- [x] Flag `is_approved` from `validation_status`
- [x] Count per-vehicle violation history for repeat offender scoring

**Verification**:
- [x] Assert record count ≈ 298,445 ± 100 → **298,445** ✅
- [x] Assert no NaT in `created_datetime` → **0 NaT** ✅
- [x] Assert all lat/lon within Bengaluru bbox → **filtered** ✅
- [x] Assert `vehicle_width_m` has no NaN (default fallback = 1.5m) → **0 NaN** ✅
- [x] Print summary stats and compare against EDA #1 findings → **summary generated** ✅

### Step 1.1.2: Road Network Loader

```
File: drishtam/data_pipeline.py → load_road_network()
```

**Tasks**:
- [x] Load `data/bengaluru_roads.graphml` via `osmnx.load_graphml()`
- [x] Convert to GeoDataFrames: `nodes, edges = ox.graph_to_gdfs(G)`
- [x] Clean `highway` column (can be list → take first element)
- [x] Parse `lanes` from OSM (int, fallback to tier estimate)
- [x] Parse `width` from OSM (float, fallback to tier estimate)
- [x] Apply `ROAD_HIERARCHY` mapping → `road_tier`, `road_tier_name`, `est_lanes`, `est_width_m`
- [x] Compute edge midpoints: `geometry.interpolate(0.5, normalized=True)` → `mid_lat`, `mid_lon`
- [x] Parse road names (handle list type)
- [x] Compute `is_link_road` flag (highway_type ends with `_link`)
- [x] Compute segment `degree` (max degree of edge endpoints) → `segment_degree`

**Verification**:
- [x] Assert edge count ≈ 393,717 ± 5000 → **393,717** ✅
- [x] Assert road network loads in reasonable time → **54.9s** ✅
- [x] Print lane/width data availability stats ✅

### Step 1.1.3: Event Data Loader

```
File: drishtam/data_pipeline.py → load_events()
```

**Tasks**:
- [x] Load `Astram event data_anonymized*.csv` (8,057 records)
- [x] Parse timestamps
- [x] Filter to Bengaluru bbox
- [x] Extract cause category (`event_cause_clean`), congestion flag (`is_congestion_event`)
- [x] Create IST temporal features matching violations

**Verification**:
- [x] Assert record count ≈ 8,057 → **8,057** ✅

---

## 1.2 Spatial Enrichment — Mapping Violations to Roads

### Step 1.2.1: KDTree Nearest-Road Matching

```
File: drishtam/data_pipeline.py → enrich_violations()
```

**Tasks**:
- [x] Build coordinate arrays: edge midpoints (lat×111000, lon×108000 for meter conversion)
- [x] Build `scipy.spatial.cKDTree` on edge midpoint coordinates
- [x] Query nearest road for each violation → `nearest_road_idx`, `dist_to_road_m`
- [x] Map road attributes: `highway_clean`, `road_tier`, `road_tier_name`, `road_lanes`, `road_width`, `road_length_m`, `road_name`, `is_link_road`, `segment_degree`
- [x] Compute `capacity_blocked_pct = (vehicle_width_m / road_width) × 100`, clipped at 100
- [x] Compute `lanes_blocked = vehicle_width_m / (road_width / road_lanes)`

**Verification**:
- [x] Assert median distance to road ≈ 19.2m → **19.2m** ✅
- [x] Assert capacity_blocked_pct mean ≈ 16.4% → **16.4%** ✅
- [x] Assert 41,236 violations block >25% → **41,236** ✅
- [x] Spot-check BSF STS Road → **5,234 violations** ✅

### Step 1.2.2: Junction Proximity Computation

```
File: drishtam/data_pipeline.py → enrich_violations() (Step 2/5)
```

**Tasks**:
- [x] Build KDTree on OSM graph nodes (these are intersections)
- [x] For each violation, find distance to nearest node → `dist_to_junction_m`
- [x] Compute `junction_degree` (how many roads meet at that junction, via `street_count`)
- [x] Flag `is_near_major_junction` (degree ≥ 4 AND distance < 50m)

**Verification**:
- [x] Junction dist nulls → **0** ✅

### Step 1.2.3: Neighborhood Density Computation

```
File: drishtam/data_pipeline.py → enrich_violations() (Step 3/5)
```

**Tasks**:
- [x] For each violation, count other violations within 300m radius using KDTree (chunked, 5K per batch)
- [x] Compute `violation_density_300m` (count) → **mean 4,202.4**
- [x] Compute `violation_density_500m` (count) → **mean 7,289.9**
- [ ] `pis_density_300m` → deferred to Phase 2 (after PIS computation)

---

## 1.3 Additional Enrichment Features

### Step 1.3.1: Temporal Context Features ✅

```
File: drishtam/data_pipeline.py → load_violations()
```

**Tasks**:
- [x] `hour_ist` (0-23)
- [x] `peak_period`: 'morning_peak' (8-10), 'midday' (10-16), 'evening_peak' (17-20), 'night' (20-8)
- [x] `enforcement_active`: 1.0 if hour_ist in [6-12], 0.1 in [16-20] gap, 0.5 otherwise
- [x] Cyclical encoding: `hour_sin = sin(2π × hour/24)`, `hour_cos = cos(2π × hour/24)`
- [x] Same for day_of_week (7-cycle): `dow_sin`, `dow_cos`

### Step 1.3.2: Violation Severity Scoring ✅

```
File: drishtam/data_pipeline.py → load_violations()
```

**Tasks**:
- [x] Create severity lookup:

| Violation Type | Severity Score | Rationale |
|---|---|---|
| DOUBLE PARKING | 1.0 | Blocks entire lane minimum |
| PARKING IN A MAIN ROAD | 0.9 | High-traffic road blocked |
| PARKING NEAR ROAD CROSSING | 0.85 | Intersection blockage + safety |
| PARKING NEAR BUSTOP/SCHOOL/HOSPITAL | 0.8 | High-pedestrian zone |
| PARKING ON FOOTPATH | 0.6 | Blocks pedestrians, forces them onto road |
| NO PARKING | 0.5 | General restricted area |
| WRONG PARKING | 0.4 | Least specific violation |

- [x] For multi-violation records, take **max severity** across all tagged types
- [x] Store as `violation_severity` (0-1 scale) → **range [0.40, 1.00]** ✅

### Step 1.3.3: Repeat Offender Scoring ✅

```
File: drishtam/data_pipeline.py → load_violations()
```

**Tasks**:
- [x] Group by `vehicle_number` → count violations
- [x] `repeat_count` = number of total violations by this vehicle → **mean 2.2, max 55**
- [x] `repeat_score` = min(1, log2(repeat_count) / log2(55)) — normalized
- [x] `is_chronic_offender` = repeat_count ≥ 11

---

## 1.4 Save Enriched Dataset ✅

### Step 1.4.1: Export

```
File: scripts/01_build_enriched_data.py
```

**Tasks**:
- [x] Run full pipeline: load → enrich → add features → save
- [x] Save to `data/violations_enriched.parquet` → **38.8 MB**
- [x] Save summary statistics to `research/06_enriched_data_summary.md`
- [x] Print feature matrix summary: shape, dtypes, null counts, distributions

**Verification checklist** — ALL PASSED ✅:

| Check | Expected | Actual | Status |
|---|---|---|---|
| Total records | ~298,445 | 298,445 | ✅ PASS |
| No NaN in core features | 0 NaN | 0 | ✅ PASS |
| capacity_blocked_pct range | [0, 100] | [2.9, 100.0] | ✅ PASS |
| dist_to_road_m reasonable | median ~19m | 19.2m | ✅ PASS |
| dist_to_junction_m filled | 0 NaN | 0 | ✅ PASS |
| violation_severity range | [0.4, 1.0] | [0.40, 1.00] | ✅ PASS |
| temporal features present | 6+ columns | 6/6 | ✅ PASS |
| BSF STS Road count | ~5,231 | 5,234 | ✅ PASS |
| High-impact count | ~41,236 | 41,236 | ✅ PASS |

**📊 Visualizations produced (saved to research/)**:
1. [x] Feature correlation matrix heatmap → `06_feature_correlation_heatmap.png`
2. [x] Pairplot of top 6 features → `06_feature_pairplot.png`
3. [x] Spatial map: violations colored by capacity_blocked_pct → `06_spatial_capacity_blocked.png`
4. [x] Temporal pattern: violations by hour, split by road_tier → `06_temporal_by_road_tier.png`
5. [x] Summary dashboard: 2×3 subplot grid → `06_enrichment_summary_dashboard.png`
6. [x] Multi-modal proximity (metro/bus stops) → `06_multimodal_proximity.png` (bonus)

---

## 1.5 Phase 1 Deliverables ✅

| Deliverable | File | Status |
|---|---|---|
| Data pipeline module | `drishtam/data_pipeline.py` (742 lines) | ✅ |
| Config module | `drishtam/config.py` (241 lines) | ✅ |
| Utils module | `drishtam/utils.py` (203 lines) | ✅ |
| Verification module | `drishtam/verification.py` (237 lines) | ✅ |
| Pipeline script | `scripts/01_build_enriched_data.py` (469 lines) | ✅ |
| Cloud wrapper | `scripts/run_phase1.py` (112 lines) | ✅ |
| Enriched dataset | `data/violations_enriched.parquet` (38.8 MB, gitignored) | ✅ |
| Research log | `research/06_enriched_data_summary.md` | ✅ |
| Visualizations | `research/06_*.png` (6 charts) | ✅ |

### Exit Criteria — ALL MET ✅:
- [x] `violations_enriched.parquet` exists and loads correctly (298,445 × 77)
- [x] All 9 verification checks pass
- [x] Research log written with all distributions
- [x] All 5+ visualization charts saved (6 total)
- [x] No hardcoded paths (everything from config.py)
- [x] Ruff formatted + linted: all checks passed
- [x] Git committed: `4fdc5fb`
