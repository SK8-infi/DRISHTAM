# DRISHTAM — Implementation Plans

> **"Quantifying the Invisible Cost of Illegal Parking"**

## Status: ✅ ALL PHASES COMPLETE

All 5 phases have been implemented and deployed. The system is live with a FastAPI backend serving model inference and a Next.js interactive dashboard.

---

## 5-Phase Execution Summary

| Phase | Name | Status | Key Outputs |
|---|---|---|---|
| **Phase 1** | Data Foundation | ✅ Complete | `violations_enriched.parquet` (298K × 87 features) |
| **Phase 2** | Impact Scoring | ✅ Complete | PIS 0-100, HDBSCAN clusters, Pareto analysis |
| **Phase 3** | GNN Propagation + Digital Twin | ✅ Complete | GBM-36D (r=0.59), Frank-Wolfe simulation |
| **Phase 4** | What-If + Forecasting | ✅ Complete | 12 scenarios, HistGBM (r=0.92), 27 experiments |
| **Phase 5** | Dashboard + Deployment | ✅ Complete | FastAPI + Next.js, 5 pages, 14 API endpoints |

---

## Detailed Phase Plans

| Document | Phase | Content |
|----------|-------|---------|
| [phase1_data_foundation.md](phase1_data_foundation.md) | Phase 1 | Data pipeline, enrichment, feature engineering |
| [phase2_impact_scoring.md](phase2_impact_scoring.md) | Phase 2 | PIS computation, HDBSCAN clustering |
| [phase3_gnn_propagation.md](phase3_gnn_propagation.md) | Phase 3 | Graph construction, GAT → GBM training |
| [phase4_whatif_and_forecasting.md](phase4_whatif_and_forecasting.md) | Phase 4 | Counterfactuals, risk forecasting |
| [phase5_dashboard_and_deployment.md](phase5_dashboard_and_deployment.md) | Phase 5 | FastAPI backend, Next.js dashboard |

## Supporting Documents

| Document | Content |
|----------|---------|
| [file_structure.md](file_structure.md) | Canonical file paths and directory structure |
| [code_quality_standards.md](code_quality_standards.md) | Ruff, Mypy, testing conventions |
| [novel_enhancements.md](novel_enhancements.md) | Novel contributions and future directions |

---

## Verification Summary

### Phase 1 Exit: ✅
- [x] `violations_enriched.parquet` — 298K records × 87 features
- [x] 9 data quality checks pass
- [x] 6 visualizations saved (`research/06_*`)

### Phase 2 Exit: ✅
- [x] PIS computed for all 298K violations (0-100, no NaN)
- [x] 10 PIS validation checks pass
- [x] Weight sensitivity analysis complete
- [x] HDBSCAN: 1,087 clusters generated
- [x] Pareto: 13.8% violations → 80% impact
- [x] 15+ visualizations saved (`research/07_*`)

### Phase 3 Exit: ✅
- [x] GBM-36D model: Spearman r=0.59 (GBM >> GNN r=0.24)
- [x] Frank-Wolfe Digital Twin: 2M extra vehicle-hours/day
- [x] 393,717 segments with impact predictions
- [x] Hidden victims analysis: zero-violation impacted roads identified
- [x] 10+ visualizations saved (`research/08_*`, `09_*`)

### Phase 4 Exit: ✅
- [x] 12 counterfactual scenarios computed (evening peak = 21× best)
- [x] Reductions verified monotonic
- [x] HistGBM: Spearman r=0.92 (27 experiments)
- [x] 344K hourly risk predictions
- [x] Patrol optimizer: 53× lift with 10 officers
- [x] 10+ visualizations saved (`research/10_*`, `11_*`)

### Phase 5 Exit: ✅
- [x] 5 dashboard pages functional (Overview, Map, What-If, Clusters, Insights)
- [x] 14 API endpoints return valid data
- [x] Map renders 393K segments as polylines
- [x] What-If simulator: live GBM re-prediction with propagation rings
- [x] Cluster Explorer: bubble map + drill-down panel
- [x] Insights: 8 live data-driven findings
- [x] Docker deployment ready (`docker-compose.yml`)

---

## Research Documentation

| File | Phase | Content |
|------|-------|---------|
| `research/01_violation_eda.md` | EDA | 298K violation analysis (18 charts) |
| `research/02_event_eda.md` | EDA | 8K event analysis (20 charts) |
| `research/03_cross_dataset_analysis.md` | EDA | Spatial correlation (12 charts) |
| `research/04_osm_road_network.md` | EDA | Road network analysis (10 charts) |
| `research/05_research_landscape.md` | Research | Literature review & gap analysis |
| `research/06_enriched_data_summary.md` | Phase 1 | Enriched data stats (6 charts) |
| `research/07_parking_impact_scores.md` | Phase 2 | PIS findings, weights, clusters (15 charts) |
| `research/08_gnn_propagation.md` | Phase 3 | GAT → GBM training results (10 charts) |
| `research/09_digital_twin_simulation.md` | Phase 3 | Frank-Wolfe simulation (8 charts) |
| `research/10_gnn_twin_retraining.md` | Phase 3 | GBM retraining with sim labels (8 charts) |
| `research/11_counterfactuals_and_forecasting.md` | Phase 4 | What-If + risk model + bias discovery |
