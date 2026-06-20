# DRISHTAM (दृष्टम्) — Project File Structure

> **Single source of truth** for all file and directory paths.  
> Every plan, module, and script MUST follow this structure.  
> Last updated: 2026-06-19 (All phases complete)

---

## Directory Tree

```
Gridlock project/
│
├── README.md                           # Project overview, architecture, setup
├── pyproject.toml                      # Project metadata, tool configs (ruff, mypy, pytest)
├── requirements.txt                    # Python dependencies
├── .gitignore                          # Tracked exclusions (data, cache, venv, logs)
├── .env.example                        # Environment variable template
├── Dockerfile.api                      # API container
├── docker-compose.yml                  # Multi-service orchestration
│
├── plans/                              # 📋 Design documents & phase plans
│   ├── README.md                       #   Plan overview & status (ALL COMPLETE)
│   ├── file_structure.md               #   THIS FILE — canonical path reference
│   ├── code_quality_standards.md       #   Ruff, Mypy, Bandit, testing, docstring conventions
│   ├── novel_enhancements.md           #   Novel layers: economic cost, carbon, equity
│   ├── phase1_data_foundation.md       #   ✅ Phase 1 plan (COMPLETE)
│   ├── phase2_impact_scoring.md        #   ✅ Phase 2 plan (COMPLETE)
│   ├── phase3_gnn_propagation.md       #   ✅ Phase 3 plan (COMPLETE)
│   ├── phase4_whatif_and_forecasting.md #   ✅ Phase 4 plan (COMPLETE)
│   └── phase5_dashboard_and_deployment.md # ✅ Phase 5 plan (COMPLETE)
│
├── drishtam/                           # 🐍 Core Python package (15 modules)
│   ├── __init__.py                     #   Package init, version, public API
│   ├── config.py                       #   All constants, paths, mappings, hyperparameters
│   ├── exceptions.py                   #   Custom exception hierarchy
│   ├── utils.py                        #   Shared helpers (coordinates, timer, I/O, validation)
│   │
│   │  # --- Phase 1: Data Foundation ---
│   ├── data_pipeline.py                #   ETL: load/enrich violations, road matching
│   ├── verification.py                 #   Quality gates, enrichment summary
│   │
│   │  # --- Phase 2: Impact Scoring ---
│   ├── impact_scorer.py                #   PIS engine: 6 components, compute_pis()
│   ├── clustering.py                   #   HDBSCAN: cluster_violations(), enforcement zones
│   │
│   │  # --- Phase 3: GNN Propagation + Digital Twin ---
│   ├── graph_builder.py                #   OSM → PyG line graph, node/edge features
│   ├── propagation_model.py            #   ParkImpactGAT model, train/predict
│   ├── traffic_simulator.py            #   Digital twin: Frank-Wolfe UE, BPR functions
│   ├── traffic_zones.py                #   80 Bengaluru landmark zones + OD demand
│   │
│   │  # --- Phase 4: What-If & Forecasting ---
│   ├── counterfactual.py               #   What-if simulation engine, 12 scenarios
│   ├── risk_forecaster.py              #   HistGBM risk prediction, 27 experiments
│   └── enforcement_optimizer.py        #   Greedy patrol scheduling, fleet comparison
│
├── scripts/                            # 🚀 Executable pipeline scripts (run in order)
│   ├── 01_build_enriched_data.py       #   Phase 1: Load → enrich → verify → save
│   ├── 02_compute_impact_scores.py     #   Phase 2: PIS → clustering → costs → viz
│   ├── 03_build_gnn_graph.py           #   Phase 3: Build PyG graph
│   ├── 03b_simulate_traffic.py         #   Phase 3: Frank-Wolfe traffic simulation
│   ├── 03c_retrain_gnn_twin.py         #   Phase 3: GBM-36D training (Colab GPU)
│   ├── 04_train_forecaster.py          #   Phase 4: 27 model experiments
│   ├── 05_generate_counterfactuals.py  #   Phase 4: 12 enforcement scenarios
│   ├── 06_optimize_enforcement.py      #   Phase 4: Greedy officer allocation
│   └── quality_check.py                #   Code quality runner (ruff, mypy, tests)
│
├── api/                                # 🌐 FastAPI Backend (live inference)
│   ├── __init__.py                     #   Package init
│   ├── main.py                         #   App entry: CORS, lifespan, router registration
│   ├── engine_loader.py                #   EngineStore singleton — loads all models at startup
│   │                                   #     query_bbox(), get_segment(), run_whatif(),
│   │                                   #     get_risk(), get_clusters(), compute_insights()
│   ├── models.py                       #   Pydantic schemas (25+ models)
│   └── routers/                        #   REST endpoint handlers
│       ├── __init__.py
│       ├── overview.py                 #     GET /api/overview
│       ├── segments.py                 #     GET /api/segments, /api/segment/{id}
│       ├── whatif.py                   #     POST /api/whatif, GET /api/whatif/roads
│       ├── risk.py                     #     GET /api/risk, /api/risk/animation
│       ├── optimizer.py                #     POST /api/optimize
│       ├── clusters.py                 #     GET /api/clusters, /api/cluster/{id}
│       ├── violations.py               #     GET /api/violations
│       └── insights.py                 #     GET /api/insights (live computed)
│
├── dashboard/                          # 🎨 Next.js 15 Frontend
│   ├── package.json                    #   Dependencies (react 19, leaflet, recharts)
│   ├── next.config.ts                  #   Next.js config (transpilePackages)
│   ├── tsconfig.json                   #   TypeScript config
│   ├── src/
│   │   ├── app/                        #   Pages (Next.js App Router)
│   │   │   ├── layout.tsx              #     Root layout (sidebar + QueryProvider)
│   │   │   ├── globals.css             #     OLED-dark design system (Plus Jakarta Sans)
│   │   │   ├── page.tsx                #     / — Overview (KPIs, Pareto, sparklines)
│   │   │   ├── map/page.tsx            #     /map — Impact Map (3 lens modes)
│   │   │   ├── whatif/page.tsx         #     /whatif — What-If Simulator
│   │   │   ├── clusters/page.tsx       #     /clusters — Cluster Explorer
│   │   │   └── insights/page.tsx       #     /insights — Executive Insights
│   │   ├── components/
│   │   │   ├── Layout/
│   │   │   │   ├── Sidebar.tsx         #     Navigation sidebar (5 pages)
│   │   │   │   └── QueryProvider.tsx   #     React Query wrapper
│   │   │   ├── Map/
│   │   │   │   ├── SegmentMap.tsx      #     Leaflet map with polyline rendering
│   │   │   │   ├── SegmentPanel.tsx    #     Slide-in segment detail panel
│   │   │   │   ├── PropagationMap.tsx  #     What-If propagation visualization
│   │   │   │   ├── ClusterBubbleMap.tsx #    Cluster bubble visualization
│   │   │   │   └── ClusterPanel.tsx    #     Cluster drill-down panel
│   │   │   ├── Charts/
│   │   │   │   ├── ParetoDonut.tsx     #     80/20 donut chart
│   │   │   │   ├── HourlyChart.tsx     #     24-hour bar chart
│   │   │   │   ├── Sparkline.tsx       #     Inline sparkline
│   │   │   │   └── TopRoadsTable.tsx   #     Top roads ranking table
│   │   │   ├── AnimatedCounter.tsx     #     Counting animation component
│   │   │   ├── ReductionGauge.tsx      #     Circular reduction gauge
│   │   │   └── MiniMapPulse.tsx        #     Pulsing map thumbnail
│   │   └── lib/
│   │       ├── api.ts                  #     Typed API client (fetch wrappers)
│   │       └── colors.ts              #     Color utilities & number formatters
│   └── public/                         #   Static assets (favicon)
│
├── data/                               # 📊 Data files (gitignored)
│   ├── violations_enriched.parquet     #   298K × 87 features (~50 MB)
│   ├── bengaluru_roads.graphml         #   OSM road network (~150 MB)
│   ├── propagated_impact.parquet       #   Impact propagation (~7 MB)
│   ├── risk_predictions.parquet        #   344K hourly predictions (~3 MB)
│   ├── counterfactual_scenarios.json   #   12 pre-computed scenarios
│   ├── risk_alerts.json                #   Current top risk alerts
│   ├── risk_summary.json               #   Risk model summary stats
│   ├── enforcement_schedule.json       #   Optimal patrol schedule
│   ├── fleet_comparison.json           #   Fleet ROI comparison
│   └── simulation/                     #   Digital twin outputs
│       ├── baseline_flows.npy          #     Equilibrium traffic flows
│       └── delay_metrics.json          #     Congestion delay calculations
│
├── models/                             # 🧠 Trained models (gitignored)
│   ├── gbm_36d_best.pkl                #   Engine 1: GBM impact predictor (5.7 MB)
│   ├── feature_scaler.pkl              #   StandardScaler for 36 features
│   ├── features_36d.npy                #   Feature matrix for all segments (57 MB)
│   ├── risk_forecaster_best.pkl        #   Engine 3: HistGBM risk model (521 KB)
│   ├── segment_predictions.parquet     #   All segments with geometry (34 MB)
│   ├── edge_list.npz                   #   Graph edge list for neighbor queries (9 MB)
│   ├── seg_betweenness.npy             #   Betweenness centrality values
│   ├── mlp_36d_best.pt                 #   MLP model (PyTorch, experimental)
│   └── ml_summary.json                 #   Model metadata and scores
│
├── research/                           # 📈 11 reports + 107 visualizations
│   ├── 01_violation_eda.md             #   EDA #1: Violation patterns (18 charts)
│   ├── 02_event_eda.md                 #   EDA #2: Traffic events (20 charts)
│   ├── 03_cross_dataset_analysis.md    #   EDA #3: Cross-dataset correlation
│   ├── 04_osm_road_network.md          #   EDA #4: Road network analysis
│   ├── 05_research_landscape.md        #   Literature review & gap analysis
│   ├── 06_enriched_data_summary.md     #   Phase 1: Enrichment summary
│   ├── 07_parking_impact_scores.md     #   Phase 2: PIS report
│   ├── 08_gnn_propagation.md           #   Phase 3: GNN results
│   ├── 09_digital_twin_simulation.md   #   Phase 3: Traffic simulation
│   ├── 10_gnn_twin_retraining.md       #   Phase 3: GBM retraining
│   ├── 11_counterfactuals_and_forecasting.md # Phase 4: What-If + risk
│   └── *.png                           #   96 chart images
│
└── archive/                            # 🗄️ Historical work (not production)
    ├── cache/                          #   Runtime caches
    ├── eda_scripts/                    #   Early EDA scripts
    ├── infra/                          #   Cloud setup scripts
    ├── logs/                           #   Execution logs
    ├── notebooks/                      #   Colab notebooks
    └── raw_data/                       #   Original CSV files
```

---

## Key File Descriptions

### API — `engine_loader.py` (the brain)

The `EngineStore` singleton is the backend's core. It loads everything at startup (~15s) and keeps it in memory:

| What It Loads | Source File | Size |
|---------------|------------|------|
| Segment predictions | `models/segment_predictions.parquet` | 393K rows, with lat/lon geometry |
| Violations | `data/violations_enriched.parquet` | 298K rows, 87 features |
| GBM model | `models/gbm_36d_best.pkl` | Impact prediction (36 features) |
| Feature matrix | `models/features_36d.npy` | 393K × 36 float64 |
| Risk predictions | `data/risk_predictions.parquet` | 344K hourly forecasts |
| Edge list | `models/edge_list.npz` | Graph neighbors for propagation |
| Scenarios | `data/counterfactual_scenarios.json` | 12 pre-computed results |
| Enforcement | `data/enforcement_schedule.json` | Patrol optimization |

### Dashboard — `api.ts` (the bridge)

Typed fetch wrappers for all 14 API endpoints. Each function returns a typed Promise matching Pydantic schemas.

### Dashboard — `globals.css` (the theme)

OLED-dark design system using `Plus Jakarta Sans`. Defines CSS custom properties for all colors, spacing, and component styles. Key tokens:
- `--bg-primary: #08080a` (pure OLED black)
- `--accent: #3b82f6` (blue-500)
- `--danger: #ef4444`, `--warning: #f97316`, `--success: #10b981`

---

## Data Flow

```
Startup (15s):
  engine_loader.py loads → segments, violations, GBM, features, risk, edges

API Request Flow:
  Client → Next.js page → api.ts fetch → FastAPI router → EngineStore method → Response

What-If Computation (live):
  1. Find road segments by name
  2. Zero out violation features in feature matrix copy
  3. GBM.predict() on modified features
  4. Compute delta = baseline - modified
  5. Classify into propagation rings (hop 0/1/2)
  6. Calculate cost-benefit ROI
  7. Return full result

Cluster Drill-Down:
  1. Filter violations by cluster_id
  2. Aggregate by road → road_breakdown
  3. Group by hour → hourly_profile
  4. Count vehicle types → vehicle_types
  5. Compute severity + capacity stats
```
