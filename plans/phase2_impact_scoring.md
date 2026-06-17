# Phase 2: Parking Impact Score (PIS) Engine + Advanced EDA

> **Goal**: Compute the per-violation Parking Impact Score (0-100) and validate it  
> **Inputs**: `violations_enriched.parquet` from Phase 1  
> **Outputs**: PIS scores for all 298K violations, hotspot clusters, validation report  
> **Dependencies**: Phase 1 complete

---

## 2.1 PIS Formula Implementation

### Step 2.1.1: Component Functions

```
File: parkimpact/impact_scorer.py
```

Each component is a standalone function that returns a 0-1 normalized score per violation.

#### Component 1: Capacity Factor (w=0.30) — THE MOST IMPORTANT

```python
def compute_capacity_factor(viol_df):
    """
    How much of the road is physically blocked by this violation?
    = vehicle_width / road_width, clipped to [0, 1]
    
    Examples:
      Car (2.0m) on 6m residential → 0.333
      Car (2.0m) on 14m primary    → 0.143
      Scooter (0.7m) on 8m tertiary → 0.088
      HGV (2.5m) on 4m living st   → 0.625
    """
```

**Verification**:
- [ ] Range is [0, 1] for all records
- [ ] Mean ≈ 0.164 (matches EDA #4 finding of 16.4% mean blocked)
- [ ] Living street values highest (~0.375 median from EDA #4)
- [ ] Arterial values lowest (~0.083 median from EDA #4)

**📊 Visualization**: Box plot of capacity_factor by road_tier_name (should match EDA #4 Fig 7)

#### Component 2: Road Importance (w=0.20)

```python
def compute_road_importance(viol_df):
    """
    How critical is this road to the overall network?
    
    Score = normalized(tier_weight × lane_factor)
    
    tier_weight:
      Expressway = 1.0, Arterial = 0.9, Primary = 0.8
      Secondary = 0.6, Tertiary = 0.4, Residential = 0.2
      Living Street = 0.1, Service = 0.05
      
    lane_factor = min(1, lanes / 4)  # More lanes = more traffic served
    
    Link roads get 1.3× multiplier (junction connectors are critical)
    """
```

**Verification**:
- [ ] Expressway/arterial violations score highest
- [ ] Link road violations score higher than their parent road types
- [ ] Distribution should be bimodal (many low from residential, bump at high from primary/arterial)

**📊 Visualization**: Histogram of road_importance colored by road tier

#### Component 3: Junction Proximity Factor (w=0.15)

```python
def compute_junction_factor(viol_df):
    """
    How close to an intersection? Violations near junctions cause cascading delays.
    
    Score = exp(-dist_to_junction / 100)
    
    At junction (0m): score = 1.0
    At 50m: score = 0.61
    At 100m: score = 0.37
    At 200m: score = 0.14
    At 500m: score = 0.007 (negligible)
    
    Bonus: multiply by junction_degree / max_degree for major junctions
    """
```

**Verification**:
- [ ] Score decreases monotonically with distance
- [ ] Link road violations should have higher junction scores (they're AT junctions)
- [ ] Mean score for link roads > mean score for parent roads

**📊 Visualization**: 
- 2D scatter: dist_to_junction vs junction_factor (should show exponential decay curve)
- Map: violations colored by junction_factor — junction clusters should glow

#### Component 4: Temporal Factor (w=0.15)

```python
def compute_temporal_factor(viol_df):
    """
    Is this during peak traffic hours?
    
    IST Hour → Score:
      8:00-10:00 AM  → 1.0  (morning peak)
      10:00-12:00 PM → 0.8  (late morning commercial)
      5:00-8:00 PM   → 1.0  (evening peak)
      12:00-5:00 PM  → 0.6  (midday)
      8:00-11:00 PM  → 0.4  (evening wind-down)
      11:00 PM-6:00 AM → 0.2 (overnight — low impact)
      6:00-8:00 AM   → 0.7  (early morning buildup)
      
    Weekend multiplier: × 0.7 (less commuter traffic)
    """
```

**Verification**:
- [ ] Peak hours (8-10 AM, 5-8 PM IST) should have max scores
- [ ] Overnight violations should have lowest scores
- [ ] Weekend should be lower than weekday at same hour
- [ ] Cross-check: the enforcement gap (3:30-8:30 PM) should show LOW enforcement but HIGH temporal_factor — this validates our "missed opportunity" finding

**📊 Visualization**:
- Heatmap: hour_ist × day_of_week → mean temporal_factor
- Overlay: enforcement_count (bars) vs temporal_factor (line) by hour — should show inverse relationship at evening

#### Component 5: Density Factor (w=0.10)

```python
def compute_density_factor(viol_df):
    """
    Are there many violations nearby? Multiple violations compound each other.
    
    Score = log1p(violations_in_300m) / log1p(max_density)
    
    Normalizes to [0, 1] where:
      0 violations nearby → 0.0
      Median density → ~0.5
      Maximum density → 1.0
    """
```

**Verification**:
- [ ] Upparpet/Shivajinagar/KR Market areas should have highest density scores
- [ ] Outskirt violations should have near-zero density
- [ ] Correlation with violation_count per grid cell (from EDA #3) should be high

**📊 Visualization**: Hexbin map colored by density_factor — should match EDA #1 hexbin density

#### Component 6: Violation Severity (w=0.10)

```python
def compute_severity_factor(viol_df):
    """
    Severity lookup from Step 1.3.2, already computed.
    DOUBLE_PARKING → 1.0
    PARKING_IN_MAIN_ROAD → 0.9
    ... etc
    """
```

**Verification**: Already verified in Phase 1.

---

### Step 2.1.2: Master PIS Computation

```python
def compute_pis(viol_df, weights=None):
    """
    PIS = Σ(wi × component_i) × 100
    
    Default weights: [0.30, 0.20, 0.15, 0.15, 0.10, 0.10]
    
    Returns: Series of PIS values, 0-100 scale
    """
```

**Tasks**:
- [ ] Compute all 6 components
- [ ] Apply weights and sum
- [ ] Scale to 0-100
- [ ] Add `pis_band` classification:

| PIS Range | Band | Color | Interpretation |
|---|---|---|---|
| 0-20 | LOW | 🟢 Green | Minimal congestion impact |
| 20-40 | MODERATE | 🟡 Yellow | Noticeable but manageable |
| 40-60 | HIGH | 🟠 Orange | Significant capacity reduction |
| 60-80 | SEVERE | 🔴 Red | Major congestion contributor |
| 80-100 | CRITICAL | ⚫ Black/Dark Red | Extreme — near-complete blockage |

**Verification (CRITICAL — all must pass)**:

| Check | Expected | Rationale |
|---|---|---|
| PIS mean | 25-45 | Most violations are moderate impact |
| PIS median | 20-35 | Right-skewed (many low, few extreme) |
| PIS std | 15-25 | Reasonable spread |
| PIS min | >0 | No zero scores (every violation has some impact) |
| PIS max | <100 | Very few should hit maximum |
| BSF STS Road mean PIS | Top 10 in city | Known worst road from EDA |
| Link road mean PIS > parent | Yes | 2-4× density finding |
| Peak hour PIS > off-peak | Yes | Temporal factor effect |
| Car PIS > Scooter PIS | Yes | Vehicle width effect |
| Correlation: PIS vs event_density (grid) | r > 0.35 | Should match/improve on EDA #3's r=0.41 |

**📊 Visualizations (CRITICAL — save all)**:
1. **PIS Distribution**: Histogram with vertical lines for mean, median, and band boundaries
2. **PIS by Road Tier**: Box plot showing PIS distribution per road hierarchy
3. **PIS Map**: Full Bengaluru map — violations colored by PIS (gradient green→yellow→red→black)
4. **PIS vs Capacity Blocked**: Scatter plot — should show positive relationship but PIS has more nuance
5. **PIS Component Breakdown**: Stacked bar for top 20 highest-PIS violations showing each component's contribution
6. **PIS Temporal Pattern**: Mean PIS by hour (IST) — should peak at rush hours
7. **PIS Top 20 Roads**: Bar chart of roads with highest mean PIS (not highest count — that's different!)
8. **PIS Validation**: Scatter of grid-level mean PIS vs event_density (from EDA #3 cross-dataset)

---

## 2.2 Weight Sensitivity Analysis

### Step 2.2.1: Weight Perturbation

**Tasks**:
- [ ] Define 5 alternative weight configurations:
  - `capacity_heavy`: [0.50, 0.15, 0.10, 0.10, 0.10, 0.05] — capacity dominates
  - `location_heavy`: [0.20, 0.30, 0.25, 0.10, 0.10, 0.05] — road/junction dominates
  - `temporal_heavy`: [0.20, 0.15, 0.10, 0.35, 0.10, 0.10] — time dominates
  - `equal`: [1/6]*6 — uniform
  - `data_driven`: weights from feature importance of random forest predicting event proximity
- [ ] Compute PIS for each configuration
- [ ] Compare: rank correlations, top-20 overlap, distribution shapes
- [ ] Select final weights based on which configuration best predicts event density (cross-validation with EDA #3)

**📊 Visualizations**:
1. **Weight comparison table**: Side-by-side top-20 roads under each weight scheme
2. **Rank correlation matrix**: Spearman r between PIS rankings under different weights
3. **Distribution overlay**: PIS histograms for each weight scheme overlaid

### Step 2.2.2: Data-Driven Weight Learning

```python
def learn_optimal_weights(viol_df, events_df, grid_size=500):
    """
    Use event density as a "ground truth" proxy.
    Train a Random Forest: features = [6 PIS components], target = event_density_in_grid_cell
    Extract feature importances → use as data-driven weights.
    """
```

**Verification**:
- [ ] Learned weights should have capacity_factor as top-1 or top-2 feature
- [ ] R² of random forest should be > 0.15 (some signal)
- [ ] Compare learned weights to expert weights — discuss differences

**📊 Visualization**: Bar chart of learned weights vs expert weights

---

## 2.3 Hotspot Clustering (HDBSCAN)

### Step 2.3.1: Spatial Clustering

```
File: parkimpact/clustering.py
```

**Tasks**:
- [ ] Run HDBSCAN on violation (lat, lon) with min_cluster_size=50
- [ ] Characterize each cluster:
  - Location (centroid lat/lon)
  - Size (violation count)
  - Mean PIS, max PIS
  - Dominant road type, mean lane count, mean road width
  - Temporal pattern (peak hour)
  - Dominant violation type
  - Area (convex hull area in m²)
  - Named roads in cluster
- [ ] Rank clusters by `aggregate_impact = sum(PIS) in cluster`
- [ ] Identify top-20 enforcement priority clusters

**Verification**:
- [ ] Expected ~30-80 clusters (depends on min_cluster_size)
- [ ] Upparpet/Shivajinagar/KR Market should be top clusters
- [ ] BSF STS Road should form its own cluster or be in a top cluster
- [ ] Noise points (unclustered) should be <30% of violations

**📊 Visualizations**:
1. **Cluster Map**: Bengaluru map with clusters colored by aggregate_impact, sized by violation count
2. **Top 20 Clusters Table**: Ranked by aggregate_impact with all stats
3. **Cluster Profile Cards**: 2×3 grid of top 6 clusters — each showing mini-map, temporal pattern, road type breakdown
4. **Cluster vs Grid Comparison**: Compare HDBSCAN clusters with grid-based quintiles from EDA #3
5. **Enforcement Zone Map**: Top 20 clusters with suggested patrol zones (convex hulls)

---

## 2.4 Phase 2 Advanced EDA

### Step 2.4.1: PIS-Driven Insights (NEW analysis not in original EDA)

These are analyses that ONLY become possible after PIS is computed:

**📊 Required visualizations**:

1. **"The Pareto Chart"**: Cumulative % of total PIS vs. % of violations sorted by PIS descending. Show where 80% of impact comes from. Expected: top ~15% of violations → ~80% of impact.

2. **"The Enforcement Gap Exposed"**: For each hour (IST), show:
   - Bar: violation count
   - Line: mean PIS
   - Annotation: enforcement status (active/inactive)
   - Key insight: evening peak has HIGH PIS violations but ZERO enforcement

3. **"Road Types That Matter"**: Stacked area chart — cumulative PIS contribution by road tier. Show that tertiary + residential = majority of impact despite being "small" roads.

4. **"Vehicle Type Impact Matrix"**: Heatmap: vehicle_type × road_tier → mean PIS. Cars on residential roads should glow hot.

5. **"The BSF STS Road Deep Dive"**: Single-road analysis — temporal pattern of PIS, vehicle types, violation types, monthly trend. Why is this road 4× worse?

6. **"Link Road Vulnerability"**: Compare link roads vs parent roads — mean PIS, count, capacity blocked. Quantify the 2-4× density finding from EDA #4 in PIS terms.

7. **"If We Only Had 100 Officers"**: Rank enforcement zones by PIS/km² → where should limited resources go?

### Step 2.4.2: Save Research Report

```
File: research/07_parking_impact_scores.md
```

**Tasks**:
- [ ] Write comprehensive findings document
- [ ] Include all charts from 2.1-2.4
- [ ] Compare PIS findings with raw EDA findings — what changed?
- [ ] Identify surprises (roads that are high-count but low-PIS, or low-count but high-PIS)
- [ ] Document weight sensitivity results
- [ ] Document clustering results

---

## 2.5 Phase 2 Deliverables

| Deliverable | File | Description |
|---|---|---|
| Impact scorer module | `parkimpact/impact_scorer.py` | PIS computation with 6 components |
| Clustering module | `parkimpact/clustering.py` | HDBSCAN clustering + characterization |
| PIS computation script | `scripts/02_compute_impact_scores.py` | End-to-end PIS pipeline |
| Updated dataset | `data/violations_enriched.parquet` | Now includes PIS + cluster_id |
| Research report | `research/07_parking_impact_scores.md` | Full findings with all charts |
| Visualizations | `research/07_*.png` | 15+ charts |

### Exit Criteria (must pass before Phase 3):
- [ ] PIS computed for all 298K violations, no NaN
- [ ] All 10 verification checks in Step 2.1.2 pass
- [ ] Weight sensitivity analysis complete — final weights chosen
- [ ] HDBSCAN clusters generated and characterized
- [ ] All 15+ visualizations saved
- [ ] Research report written
- [ ] Pareto chart confirms top ~15% → ~80% of impact (validates our approach)
- [ ] PIS-event cross-validation: grid-level Spearman r ≥ 0.35
