# Phase 4: Counterfactual What-If Engine + Risk Forecaster ✅ COMPLETE

> **Goal**: Build the "What-If" simulator (Engine 2) and the predictive risk forecaster (Engine 3)  
> **Inputs**: PIS scores, GBM-36D model, enriched violations  
> **Outputs**: 12 scenarios, HistGBM risk forecaster (r=0.92), patrol optimizer (53× lift)  
> **Status**: ✅ COMPLETE — 27 experiments, enforcement bias discovery

---

## 4.1 Counterfactual What-If Engine (ENGINE 2)

### Step 4.1.1: Baseline Impact Computation

```
File: drishtam/counterfactual.py → compute_baseline_impact()
```

**Tasks**:
- [ ] Current state: all 298K violations active on the graph
- [ ] Compute total propagated impact across entire city: `Σ(propagated_impact_per_segment)`
- [ ] Also compute per-region baselines (North, South, East, West, Central)
- [ ] Store as the "do nothing" baseline

**Metrics to compute**:

| Metric | Description |
|---|---|
| `total_impact` | Sum of propagated impact across all road segments |
| `affected_segments` | Number of segments with propagated impact > threshold |
| `mean_impact` | Average propagated impact per segment |
| `critical_segments` | Segments with propagated impact > 0.7 |
| `total_capacity_lost_km` | Estimated km of effective road capacity removed |

### Step 4.1.2: Intervention Simulator

```
File: drishtam/counterfactual.py → simulate_intervention()
```

**Tasks**:
- [ ] Accept a `removal_mask` (which violations to "remove")
- [ ] Remove masked violations from the graph node features
- [ ] Re-run GAT forward pass with updated features → new propagated scores
- [ ] Compute `Δ_impact = baseline_total - intervention_total`
- [ ] Compute `pct_reduction = Δ_impact / baseline_total × 100`
- [ ] Compute per-segment delta (which segments improved most?)

**Verification**:
- [ ] Removing ALL violations → impact should drop to near-zero (sanity check)
- [ ] Removing zero violations → impact should match baseline exactly
- [ ] Removing top-1 violation → very small change (< 0.01%)
- [ ] Changes should be monotonic: removing more violations → more reduction

### Step 4.1.3: Pre-Computed Scenarios

**Tasks**: Define and run these scenarios:

| # | Scenario | Selection Criteria | Expected |
|---|---|---|---|
| S1 | **Remove top 10 named roads** | Top 10 by aggregate PIS | ~15-25% reduction |
| S2 | **Remove top 50 named roads** | Top 50 by aggregate PIS | ~30-50% reduction |
| S3 | **Remove all CRITICAL PIS** | PIS > 80 | ~20-30% reduction |
| S4 | **Remove all >25% blockage** | capacity_blocked > 25% (41K viols) | ~35-50% reduction |
| S5 | **Remove BSF STS Road only** | road_name = BSF STS Road | ~2-5% reduction |
| S6 | **Enforce evening peak only** | Add enforcement 3:30-8:30 PM IST | ~10-20% reduction |
| S7 | **Remove top 20 HDBSCAN clusters** | Top 20 clusters by aggregate PIS | ~40-60% reduction |
| S8 | **Remove all car violations** | vehicle_type = CAR | ~30-40% reduction |
| S9 | **Remove link road violations** | is_link_road = True | ~15-25% reduction |
| S10 | **Upgrade top 5 roads to 4-lane** | Simulate width increase: 6m→12m | ~5-15% reduction |
| S11 | **Remove repeat offenders (11+)** | 552 chronic vehicles | ~3-8% reduction |
| S12 | **100 officers, optimal deployment** | Top 100 enforcement zones by PIS/km² | ~20-35% reduction |

For each scenario, record:
- Total impact before/after
- % reduction
- Top 10 segments with biggest improvement
- Affected area (map overlay)
- "Cost-benefit": violations removed vs. % reduction

**📊 Visualizations (ALL scenarios)**:

1. **"The Reduction Ladder"**: Bar chart of all 12 scenarios ranked by % reduction. Shows which interventions give the most bang for the buck.

2. **"Before/After Maps"** (for top 3 scenarios): Side-by-side maps showing propagated impact before and after intervention. Color gradient: green (improved) → grey (unchanged) → red (worsened).

3. **"Pareto Frontier"**: Scatter of (# violations removed) vs (% impact reduction) for all scenarios. Find the efficient frontier — which scenarios are "dominated"?

4. **"BSF STS Road Ripple Effect"**: Animated/multi-panel showing what happens when you enforce BSF STS Road: which nearby segments see the biggest improvement?

5. **"The 100 Officers Problem"**: Map showing optimal deployment of 100 enforcement units. Size circles by PIS/km². Show estimated coverage and impact reduction.

6. **"Scenario Dashboard"**: 4×3 grid of mini-maps, one per scenario, showing the intervention effect.

### Step 4.1.4: Interactive What-If API Preparation

**Tasks**:
- [ ] Create function `interactive_whatif(road_names: List[str]) → dict` that:
  1. Identifies all violations on those roads
  2. Runs intervention simulation
  3. Returns: baseline impact, new impact, % reduction, affected segment list
- [ ] Optimize for speed: pre-compute node features for common roads
- [ ] Response time target: <2 seconds for single road query
- [ ] Cache scenario results for common queries

**Verification**:
- [ ] Single road query returns in <5 seconds
- [ ] Results are consistent (same input → same output)
- [ ] Edge cases: unknown road name → graceful error

---

## 4.2 Risk Forecaster (ENGINE 3)

### Step 4.2.1: Feature Engineering for Prediction

```
File: drishtam/risk_forecaster.py → build_prediction_features()
```

**Target variable**: For each (road_segment, time_slot) pair:
```
risk_score = historical_violation_probability × expected_mean_PIS
```

This is the "expected impact if violations occur as historically predicted."

**Feature matrix** (per road segment × time slot):

| Category | Feature | Type | Source |
|---|---|---|---|
| **Temporal** | hour_sin, hour_cos | Float | Cyclical encoding of IST hour |
| **Temporal** | dow_sin, dow_cos | Float | Cyclical encoding of day of week |
| **Temporal** | month_sin, month_cos | Float | Cyclical encoding of month |
| **Temporal** | is_weekend | Binary | |
| **Temporal** | is_peak_morning | Binary | 8-10 AM IST |
| **Temporal** | is_peak_evening | Binary | 5-8 PM IST |
| **Spatial** | road_tier | Cat/Int | From OSM |
| **Spatial** | lane_count | Int | From OSM |
| **Spatial** | road_width_m | Float | From OSM |
| **Spatial** | road_length_m | Float | From OSM |
| **Spatial** | is_link_road | Binary | From OSM |
| **Spatial** | junction_degree_max | Int | Max degree of endpoint junctions |
| **Historical** | hist_violation_rate_hour | Float | Historical violations/day at this hour |
| **Historical** | hist_mean_pis | Float | Historical mean PIS on this segment |
| **Historical** | hist_max_pis | Float | Historical max PIS on this segment |
| **Historical** | hist_capacity_blocked | Float | Historical mean capacity blocked |
| **Neighborhood** | neighbor_violation_rate_300m | Float | Rate in 300m radius |
| **Neighborhood** | neighbor_mean_pis_300m | Float | Mean PIS in 300m radius |
| **Cluster** | cluster_id | Cat | HDBSCAN cluster assignment |
| **Cluster** | cluster_aggregate_pis | Float | Total PIS in cluster |

Total: ~22 features

**Tasks**:
- [ ] Create time slots: 24 hours × 7 days = 168 slots per week
- [ ] For each (segment, time_slot): compute historical violation rate
- [ ] Only include segments with ≥3 historical violations (filter noise)
- [ ] Compute all features above
- [ ] Split: Temporal split — train on Jan-Mar, test on Apr
  - Train: ~75% of data
  - Test: ~25% of data (April — unseen future)
- [ ] Handle class imbalance: most segment-hours have zero violations

**Verification**:
- [ ] Feature matrix has no NaN
- [ ] Train/test split is temporal (no leakage)
- [ ] At least 1000 positive samples in test set

### Step 4.2.2: Model Training

```
File: drishtam/risk_forecaster.py → train_risk_model()
```

**Primary model: XGBoost**
```python
params = {
    'objective': 'reg:squarederror',
    'max_depth': 8,
    'learning_rate': 0.05,
    'n_estimators': 500,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 5,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'tree_method': 'gpu_hist',  # Use GPU!
    'eval_metric': 'rmse'
}
```

**Secondary model: LightGBM** (for ensemble)
```python
params = {
    'objective': 'regression',
    'max_depth': 8,
    'learning_rate': 0.05,
    'n_estimators': 500,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 5,
    'device': 'gpu'
}
```

**Ensemble**: Average predictions from both models.

**Tasks**:
- [ ] Train XGBoost with early stopping on validation set
- [ ] Train LightGBM with early stopping
- [ ] Compute ensemble predictions
- [ ] Evaluate: RMSE, MAE, Spearman r, R² on test set
- [ ] For binary task (will violation occur? threshold > 0): AUC, precision, recall, F1

**Verification**:
- [ ] Test RMSE < train RMSE × 1.5 (not severely overfitting)
- [ ] Spearman r > 0.5 on test (good ranking ability)
- [ ] R² > 0.15 on test (some predictive power, not just noise)
- [ ] AUC > 0.75 for binary violation occurrence task
- [ ] Feature importance: top features should be intuitive (hist_violation_rate, road_width, etc.)

### Step 4.2.3: SHAP Explainability

```
File: drishtam/risk_forecaster.py → generate_shap_explanations()
```

**Tasks**:
- [ ] Compute SHAP values for XGBoost model
- [ ] Identify top 10 features by mean |SHAP|
- [ ] Compute SHAP for specific interesting predictions:
  - BSF STS Road at peak hour → which features drive high risk?
  - A low-risk segment → which features keep it safe?
- [ ] Create individual explanations for top-5 highest risk predictions

**📊 Visualizations (CRITICAL for presentation)**:

1. **SHAP Summary Plot (Beeswarm)**: All features, colored by value. The "money chart" for explainability.

2. **SHAP Bar Plot**: Mean |SHAP| per feature — simple feature importance.

3. **SHAP Dependence Plots**: For top 4 features — show how feature value affects prediction, colored by interaction feature.

4. **SHAP Waterfall**: For BSF STS Road at 9 AM — show exactly how each feature pushes the prediction up/down.

5. **SHAP Force Plot**: For a few individual predictions — visual breakdown.

### Step 4.2.4: Risk Map Generation

```
File: drishtam/risk_forecaster.py → generate_risk_maps()
```

**Tasks**:
- [ ] For each of 24 hours (typical weekday), predict risk for all segments
- [ ] Create GeoJSON output: segment geometry + risk_score + risk_band
- [ ] Create 24-frame "animation data" for the dashboard
- [ ] Generate "alert list": top 20 segments by risk for each hour
- [ ] Identify "persistent high-risk" segments (high risk at ALL hours)
- [ ] Identify "peak-only" segments (high risk only during peaks)

**📊 Visualizations**:

1. **"24-Hour Risk Animation"**: 4×6 grid of mini-maps (one per hour), showing risk distribution evolving through the day. Dawn → morning rush (hot!) → midday (cooling) → evening rush (hot!) → night (cool).

2. **"The Risk Clock"**: Circular/polar plot showing aggregate risk by hour (like a clock face). Peak hours should glow.

3. **"Persistent vs Peak-Only Hotspots"**: Map with two colors — red = always high risk, orange = peak-only risk.

4. **"Top 20 Alert Dashboard"**: Table/card layout showing top 20 highest-risk segments for "right now" (current hour), with road name, risk score, contributing factors.

5. **"Risk vs Enforcement Gap"**: Overlay risk scores with enforcement activity data. Show where risk is highest but enforcement is absent (the gap we found in EDA #1).

---

## 4.3 Integration Testing

### Step 4.3.1: End-to-End Pipeline Test

**Tasks**:
- [ ] Run full pipeline: raw data → enrichment → PIS → graph → GAT → counterfactuals → forecasting
- [ ] Verify all outputs are consistent
- [ ] Check cross-references: Do high-PIS areas match high-risk areas?
- [ ] Compare counterfactual results with risk predictions: removing high-risk areas should reduce impact most

**📊 Visualization**:
- **"The Three Views"**: 1×3 panel showing same area under:
  1. PIS view (violation-level impact)
  2. Propagated view (network-level impact)  
  3. Risk view (predicted future impact)
- Caption: "Past → Present → Future"

---

## 4.4 Phase 4 Deliverables

| Deliverable | File | Description |
|---|---|---|
| Counterfactual engine | `drishtam/counterfactual.py` | What-if simulation |
| Risk forecaster | `drishtam/risk_forecaster.py` | XGBoost + LightGBM prediction |
| Counterfactual script | `scripts/05_generate_counterfactuals.py` | Run all 12 scenarios |
| Forecaster training | `scripts/04_train_forecaster.py` | Train + evaluate + SHAP |
| Scenario results | `data/counterfactual_scenarios.json` | Pre-computed scenario results |
| Risk predictions | `data/risk_predictions.parquet` | Per-segment-per-hour risk |
| Trained models | `data/models/xgb_risk.json`, `lgb_risk.txt` | Model checkpoints |
| SHAP data | `data/shap_values.parquet` | SHAP explanations |
| Research report | `research/09_counterfactuals_and_forecasting.md` | Full findings |
| Visualizations | `research/09_*.png` | 15+ charts |

### Exit Criteria:
- [ ] All 12 counterfactual scenarios computed
- [ ] Results are physically reasonable (0.01% < reduction < 99%)
- [ ] XGBoost test Spearman r > 0.50
- [ ] SHAP analysis complete — top features identified
- [ ] 24-hour risk maps generated
- [ ] Alert system produces sensible top-20 lists
- [ ] Integration test passes (PIS ↔ propagation ↔ risk are consistent)
- [ ] Research report written with all charts
