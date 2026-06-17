# Phase 1: Data Foundation & Enrichment Pipeline

> **Goal**: Build the rock-solid data layer that everything depends on.  
> **Inputs**: Raw CSVs + OSM GraphML  
> **Outputs**: `violations_enriched.parquet` with 40+ features per violation  
> **Estimated time**: Core pipeline build

---

## 1.1 Data Loading & Cleaning Module

### Step 1.1.1: Violation Data Loader

```
File: parkimpact/data_pipeline.py → load_violations()
```

**Tasks**:
- [ ] Load `jan to may police violation_anonymized791b166.csv` (298K records)
- [ ] Parse `created_datetime` → pd.Timestamp
- [ ] Drop NaT rows (only ~5)
- [ ] Filter to Bengaluru bbox: lat ∈ [12.7, 13.4], lon ∈ [77.3, 77.9]
- [ ] Parse `violation_type` — split multi-violation records (comma-separated)
- [ ] Create `is_congestion_relevant` flag for: PARKING IN A MAIN ROAD, DOUBLE PARKING, PARKING NEAR ROAD CROSSING, PARKING NEAR BUSTOP/SCHOOL/HOSPITAL
- [ ] Create IST datetime column: `created_datetime_ist = created_datetime + 5:30`
- [ ] Extract temporal features: `hour_ist`, `day_of_week`, `month`, `is_weekend`, `is_peak_morning` (8-10 AM), `is_peak_evening` (5-8 PM)
- [ ] Parse `vehicle_type` → map to `vehicle_width_m` using lookup table
- [ ] Flag `is_approved` from `validation_status`
- [ ] Count per-vehicle violation history for repeat offender scoring

**Verification**:
- [ ] Assert record count ≈ 298,445 ± 100
- [ ] Assert no NaT in `created_datetime`
- [ ] Assert all lat/lon within Bengaluru bbox
- [ ] Assert `vehicle_width_m` has no NaN (default fallback = 1.5m)
- [ ] Print summary stats and compare against EDA #1 findings

### Step 1.1.2: Road Network Loader

```
File: parkimpact/data_pipeline.py → load_road_network()
```

**Tasks**:
- [ ] Load `data/bengaluru_roads.graphml` via `osmnx.load_graphml()`
- [ ] Convert to GeoDataFrames: `nodes, edges = ox.graph_to_gdfs(G)`
- [ ] Clean `highway` column (can be list → take first element)
- [ ] Parse `lanes` from OSM (int, fallback to tier estimate)
- [ ] Parse `width` from OSM (float, fallback to tier estimate)
- [ ] Apply `ROAD_HIERARCHY` mapping → `road_tier`, `road_tier_name`, `est_lanes`, `est_width_m`
- [ ] Compute edge midpoints: `geometry.interpolate(0.5, normalized=True)` → `mid_lat`, `mid_lon`
- [ ] Parse road names (handle list type)
- [ ] Compute `is_link_road` flag (highway_type ends with `_link`)
- [ ] Compute segment `degree` (number of connections at each endpoint)

**Verification**:
- [ ] Assert edge count ≈ 393,717 ± 5000
- [ ] Assert total road length ≈ 24,238 km ± 500
- [ ] Assert road type distribution matches EDA #4 (residential = ~81.8%)
- [ ] Print lane/width data availability stats

### Step 1.1.3: Event Data Loader

```
File: parkimpact/data_pipeline.py → load_events()
```

**Tasks**:
- [ ] Load `Astram event data_anonymized*.csv` (8,057 records)
- [ ] Parse timestamps
- [ ] Filter to Bengaluru bbox
- [ ] Extract cause category, planned/unplanned flag
- [ ] Create IST temporal features matching violations

**Verification**:
- [ ] Assert record count ≈ 8,057
- [ ] Assert cause distribution matches EDA #2 (vehicle_breakdown ≈ 60.6%)

---

## 1.2 Spatial Enrichment — Mapping Violations to Roads

### Step 1.2.1: KDTree Nearest-Road Matching

```
File: parkimpact/data_pipeline.py → enrich_violations()
```

**Tasks**:
- [ ] Build coordinate arrays: edge midpoints (lat×111000, lon×108000 for meter conversion)
- [ ] Build `scipy.spatial.cKDTree` on edge midpoint coordinates
- [ ] Query nearest road for each violation → `nearest_road_idx`, `dist_to_road_m`
- [ ] Map road attributes: `road_type`, `road_tier`, `road_tier_name`, `road_lanes`, `road_width`, `road_length`, `road_name`, `is_link_road`
- [ ] Compute `capacity_blocked_pct = (vehicle_width_m / road_width) × 100`, clipped at 100
- [ ] Compute `lanes_blocked = vehicle_width_m / (road_width / road_lanes)`

**Verification**:
- [ ] Assert median distance to road ≈ 19.2m (from EDA #4)
- [ ] Assert 95.1% within 100m
- [ ] Assert capacity_blocked_pct mean ≈ 16.4%
- [ ] Assert 41,236 violations block >25% (from EDA #4)
- [ ] Spot-check BSF STS Road: should have ~5,231 violations

### Step 1.2.2: Junction Proximity Computation

```
File: parkimpact/data_pipeline.py → compute_junction_proximity()
```

**Tasks**:
- [ ] Build KDTree on OSM graph nodes (these are intersections)
- [ ] For each violation, find distance to nearest node → `dist_to_junction_m`
- [ ] Compute `junction_degree` (how many roads meet at that junction)
- [ ] Flag `is_near_major_junction` (degree ≥ 4 AND distance < 50m)

**Verification**:
- [ ] Plot distribution of `dist_to_junction_m` — should be right-skewed, most < 200m
- [ ] Verify link road violations have shorter junction distances (EDA #4 finding)

**📊 EDA to produce**: 
- Histogram of junction distances
- Scatter: junction_distance vs capacity_blocked — is there a relationship?
- Top 20 junctions by combined violation count within 50m radius

### Step 1.2.3: Neighborhood Density Computation

```
File: parkimpact/data_pipeline.py → compute_neighborhood_density()
```

**Tasks**:
- [ ] For each violation, count other violations within 300m radius using KDTree
- [ ] Compute `violation_density_300m` (count)
- [ ] Compute `violation_density_500m` (count, for cross-reference with grid EDA)
- [ ] Compute `pis_density_300m` (will be filled in Phase 2 after PIS computation)

**Verification**:
- [ ] Mean density should roughly match EDA #3 proximity stats (median ~115 events had 115 violations within 300m)
- [ ] High-density zones should correspond to Upparpet, Shivajinagar, KR Market areas

**📊 EDA to produce**:
- Density map: hexbin of violation_density_300m values
- Comparison with EDA #1 hotspot map — should align

---

## 1.3 Additional Enrichment Features

### Step 1.3.1: Temporal Context Features

```
File: parkimpact/data_pipeline.py → add_temporal_features()
```

**Tasks**:
- [ ] `hour_ist` (0-23) — already computed
- [ ] `peak_period`: 'morning_peak' (8-10), 'midday' (10-16), 'evening_peak' (17-20), 'night' (20-8)
- [ ] `enforcement_active`: 1 if hour_ist in [5:30-12:30], 0 if in [15:30-20:30] gap, 0.5 otherwise
- [ ] Cyclical encoding: `hour_sin = sin(2π × hour/24)`, `hour_cos = cos(2π × hour/24)`
- [ ] Same for day_of_week (7-cycle) and month (12-cycle)

### Step 1.3.2: Violation Severity Scoring

```
File: parkimpact/data_pipeline.py → compute_violation_severity()
```

**Tasks**:
- [ ] Create severity lookup:

| Violation Type | Severity Score | Rationale |
|---|---|---|
| DOUBLE PARKING | 1.0 | Blocks entire lane minimum |
| PARKING IN A MAIN ROAD | 0.9 | High-traffic road blocked |
| PARKING NEAR ROAD CROSSING | 0.85 | Intersection blockage + safety |
| PARKING NEAR BUSTOP/SCHOOL/HOSPITAL | 0.8 | High-pedestrian zone |
| PARKING ON FOOTPATH | 0.6 | Blocks pedestrians, forces them onto road |
| NO PARKING | 0.5 | General restricted area |
| WRONG PARKING | 0.4 | Least specific violation |

- [ ] For multi-violation records, take **max severity** across all tagged types
- [ ] Store as `violation_severity` (0-1 scale)

### Step 1.3.3: Repeat Offender Scoring

```
File: parkimpact/data_pipeline.py → compute_repeat_offender_score()
```

**Tasks**:
- [ ] Group by `vehicle_number` → count violations
- [ ] `repeat_count` = number of total violations by this vehicle
- [ ] `repeat_score` = min(1, log2(repeat_count) / log2(55)) — normalized, max offender = 55 violations = 1.0
- [ ] `is_chronic_offender` = repeat_count ≥ 11

**📊 EDA to produce**:
- Repeat offenders: where do they park? Spatial distribution of chronic offenders
- Do repeat offenders park on higher-impact roads?

---

## 1.4 Save Enriched Dataset

### Step 1.4.1: Export

```
File: scripts/01_build_enriched_data.py
```

**Tasks**:
- [ ] Run full pipeline: load → enrich → add features → save
- [ ] Save to `data/violations_enriched.parquet`
- [ ] Save summary statistics to `research/06_enriched_data_summary.md`
- [ ] Print feature matrix summary: shape, dtypes, null counts, distributions

**Verification checklist** (ALL must pass before proceeding to Phase 2):

| Check | Expected | How |
|---|---|---|
| Total records | ~298,445 | `len(df)` |
| No NaN in core features | 0 NaN | `df[core_cols].isna().sum()` |
| capacity_blocked_pct range | [0, 100] | `df['capacity_blocked_pct'].describe()` |
| dist_to_road_m reasonable | median ~19m | `df['dist_to_road_m'].median()` |
| dist_to_junction_m filled | 0 NaN | check |
| violation_severity range | [0.4, 1.0] | `df['violation_severity'].describe()` |
| temporal features present | 6+ columns | check dtypes |
| BSF STS Road count | ~5,231 | `df[df.road_name=='BSF STS Road']` |
| High-impact count | ~41,236 | `(df.capacity_blocked_pct > 25).sum()` |

**📊 Visualizations to produce (save to research/)**:
1. Feature correlation matrix heatmap (all numeric features)
2. Pairplot of top 6 features (capacity_blocked, road_width, lanes, dist_junction, severity, density)
3. Spatial map: violations colored by capacity_blocked_pct
4. Temporal pattern: violations by hour, split by road_tier
5. Summary dashboard: 2×3 subplot grid with key distribution plots

---

## 1.5 Phase 1 Deliverables

| Deliverable | File | Description |
|---|---|---|
| Data pipeline module | `parkimpact/data_pipeline.py` | All loading + enrichment functions |
| Config module | `parkimpact/config.py` | All constants, paths, mappings |
| Utils module | `parkimpact/utils.py` | Shared helpers |
| Pipeline script | `scripts/01_build_enriched_data.py` | End-to-end executable |
| Enriched dataset | `data/violations_enriched.parquet` | 298K records × 40+ features |
| Research log | `research/06_enriched_data_summary.md` | Stats + plots from enrichment |
| Visualizations | `research/06_*.png` | 5+ plots from enrichment EDA |

### Exit Criteria (must pass before Phase 2):
- [ ] `violations_enriched.parquet` exists and loads correctly
- [ ] All 9 verification checks pass
- [ ] Research log written with all distributions
- [ ] All 5 visualization charts saved
- [ ] No hardcoded paths (everything from config.py)
