# ParkImpact — Master Implementation Plan

> **"Quantifying the Invisible Cost of Illegal Parking"**

---

## Project Overview

ParkImpact is a unified AI platform that combines **three engines** to solve the parking-congestion problem:

| Engine | Purpose | Core ML | Output |
|---|---|---|---|
| **ENGINE 1** | Impact Scoring + Propagation | PIS formula + GAT on road graph | Per-violation score 0-100 + network propagation |
| **ENGINE 2** | What-If Simulator | Counterfactual estimation | "Remove Road X → Y% congestion reduction" |
| **ENGINE 3** | Risk Forecaster | XGBoost + LightGBM + SHAP | "Tomorrow at 10 AM, these 20 roads are highest risk" |

---

## Code Quality & Security

All code must pass quality gates before proceeding to next phase.  
📋 Full standards: [code_quality_standards.md](code_quality_standards.md)

| Tool | Purpose | Command |
|---|---|---|
| **Ruff** | Lint + Format + Security | `ruff check . --fix` / `ruff format .` |
| **Mypy** | Static type checking | `mypy parkimpact/` |
| **Bandit** | Security vulnerability scan | `bandit -r parkimpact/ -c pyproject.toml` |
| **Pytest** | Unit + integration tests (≥60% coverage) | `pytest --cov` |
| **All at once** | Run everything | `python scripts/quality_check.py` |

---

## 5-Phase Execution Plan

| Phase | Name | Focus | Depends On | Detailed Plan |
|---|---|---|---|---|
| **Phase 1** | Data Foundation | Data pipeline, enrichment, feature engineering | EDA (done) | [phase1_data_foundation.md](phase1_data_foundation.md) |
| **Phase 2** | Impact Scoring | PIS computation, weight tuning, HDBSCAN clusters | Phase 1 | [phase2_impact_scoring.md](phase2_impact_scoring.md) |
| **Phase 3** | GNN Propagation | Graph construction, GAT training, propagation | Phase 2 | [phase3_gnn_propagation.md](phase3_gnn_propagation.md) |
| **Phase 4** | What-If + Forecasting | Counterfactuals, XGBoost, SHAP | Phases 2+3 | [phase4_whatif_and_forecasting.md](phase4_whatif_and_forecasting.md) |
| **Phase 5** | Dashboard + Deploy | FastAPI, Next.js, 7 pages, cloud | Phases 1-4 | [phase5_dashboard_and_deployment.md](phase5_dashboard_and_deployment.md) |

---

## Visualization Manifest

Every phase produces visualizations. Total expected: **60+ charts**.

### Phase 1 Visualizations (5+):
- Feature correlation heatmap
- Pairplot of top 6 features
- Spatial map colored by capacity_blocked
- Temporal patterns by road tier
- Summary dashboard (2×3 grid)

### Phase 2 Visualizations (15+):
- PIS distribution histogram
- PIS by road tier (box plot)
- PIS map (full Bengaluru, gradient)
- PIS component breakdown (stacked bar)
- PIS temporal pattern
- PIS top 20 roads
- PIS validation scatter
- Weight sensitivity comparison
- Pareto chart (cumulative impact)
- Enforcement gap chart
- Vehicle × Road tier heatmap
- BSF STS Road deep dive
- HDBSCAN cluster map
- Top 20 cluster profiles
- Enforcement zone map

### Phase 3 Visualizations (10+):
- Graph statistics
- Feature correlation matrix (12×12)
- Training curves
- Prediction scatter
- "The Congestion Ripple" (full city propagation)
- "Before vs After Propagation" (side-by-side)
- "The Hidden Victims" (zero-violation impacted roads)
- "Propagation Cascade" (BSF STS Road example)
- "3 Heatmap Comparison" (count vs PIS vs propagated)
- Attention weight analysis

### Phase 4 Visualizations (15+):
- "The Reduction Ladder" (12 scenarios ranked)
- Before/after maps (top 3 scenarios)
- Pareto frontier (effort vs. reduction)
- "BSF STS Road Ripple Effect"
- "100 Officers Problem" map
- Scenario comparison grid (12 mini-maps)
- SHAP beeswarm
- SHAP bar plot
- SHAP dependence plots (4)
- SHAP waterfall
- 24-hour risk animation (4×6 grid)
- Risk clock (polar chart)
- Persistent vs peak-only hotspots
- Risk vs enforcement gap
- "The Three Views" (PIS → Propagated → Risk)

### Phase 5 Visualizations (Dashboard — interactive):
- Overview dashboard (6 KPIs + map + charts)
- Full-screen impact map (interactive)
- Hotspot explorer (clusters + profiles)
- What-if simulator (before/after maps)
- Risk forecast (time slider + animation)
- Propagation viewer (ripple animation)
- Insights page (embedded charts)

---

## Verification Summary

Every phase has strict exit criteria. Here's the combined checklist:

### Phase 1 Exit:
- [ ] `violations_enriched.parquet` exists (298K records × 40+ features)
- [ ] 9 data quality checks pass
- [ ] 5+ visualizations saved

### Phase 2 Exit:
- [ ] PIS computed for all 298K violations (0-100, no NaN)
- [ ] 10 PIS validation checks pass
- [ ] Weight sensitivity analysis complete
- [ ] HDBSCAN clusters generated
- [ ] Pareto: top ~15% violations → ~80% impact
- [ ] PIS-event cross-validation: Spearman r ≥ 0.35
- [ ] 15+ visualizations saved

### Phase 3 Exit:
- [ ] GAT model trains successfully
- [ ] Val Spearman r > 0.30
- [ ] Propagated scores for all ~393K segments
- [ ] "Hidden victims" analysis complete (>100 zero-violation impacted roads)
- [ ] 10+ visualizations saved

### Phase 4 Exit:
- [ ] 12 counterfactual scenarios computed
- [ ] Reductions are physically reasonable
- [ ] XGBoost test Spearman r > 0.50
- [ ] SHAP analysis complete
- [ ] 24-hour risk maps generated
- [ ] 15+ visualizations saved

### Phase 5 Exit:
- [ ] 7 dashboard pages functional
- [ ] All API endpoints return valid data
- [ ] Map renders 298K points smoothly
- [ ] What-if simulator works
- [ ] Risk animation plays
- [ ] Deployed to cloud

---

## Research Documentation Manifest

All findings logged in `research/`:

| File | Phase | Content |
|---|---|---|
| `01_violation_eda.md` | EDA | 298K violation analysis (15 charts) |
| `02_event_eda.md` | EDA | 8K event analysis (20 charts) |
| `03_cross_dataset_analysis.md` | EDA | Correlation analysis (9 charts) |
| `04_osm_road_network.md` | EDA | Road network analysis (8 charts) |
| `05_research_landscape.md` | Research | Literature review, gap analysis, approach |
| `06_enriched_data_summary.md` | Phase 1 | Enriched data stats + distributions |
| `07_parking_impact_scores.md` | Phase 2 | PIS findings, weights, clusters |
| `08_gnn_propagation.md` | Phase 3 | GAT training, propagation results |
| `09_counterfactuals_and_forecasting.md` | Phase 4 | What-if results, risk model, SHAP |
