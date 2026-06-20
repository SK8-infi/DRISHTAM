<div align="center">

# दृष्टम् — DRISHTAM

### *"That which has been revealed."*

**Predictive Enforcement Intelligence for Urban Parking-Induced Congestion**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![scikit-learn](https://img.shields.io/badge/sklearn-1.7+-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)

---

*Every day, **298,000 parking violations** choke Bengaluru's roads.*
*But not all violations are equal.*
*A car on a 6-meter residential street blocks **33% of capacity**.*
*The same car on a 14-meter primary road blocks just 14%.*

**DRISHTAM reveals the invisible cost of every illegally parked vehicle — and tells the police exactly where, when, and how many officers to deploy.**

</div>

---

## The Problem

Bengaluru Traffic Police (BTP) receives ~300K parking violation reports annually from Astram cameras. Today, every violation is treated equally — a ₹500 fine regardless of whether it's on an empty residential street or a choked arterial during rush hour.

**Three gaps in current enforcement:**
1. **No impact quantification** — Which violations actually cause congestion?
2. **No network awareness** — A violation on Outer Ring Road cascades differently than one on a side street
3. **Reactive deployment** — Officers patrol randomly; no prediction of where violations will occur

## The Solution

DRISHTAM is a **full-stack enforcement intelligence system** with a live model-backed FastAPI backend and an interactive Next.js dashboard.

| Question | Engine | Answer |
|----------|--------|--------|
| *"How much does this violation hurt traffic?"* | **Engine 1** — Impact Predictor | PIS score 0-100 per violation |
| *"What if we enforce Road X?"* | **Engine 2** — What-If Simulator | "4.1% congestion reduction" |
| *"Where will violations happen at 9 AM?"* | **Engine 3** — Risk Forecaster | Top-20 roads per hour |
| *"Where should I send 50 officers?"* | **Optimizer** — Patrol Scheduler | 37.6× better than random |

---

## System Architecture

```
                          ┌─────────────────────────────────────────────┐
                          │           DRISHTAM दृष्टम्                  │
                          │   Predictive Enforcement Intelligence       │
                          ├─────────────────────────────────────────────┤
                          │                                             │
 ┌──────────────┐   ┌─────┴──────┐   ┌──────────────┐   ┌────────────┐│
 │  ENGINE 1    │   │  ENGINE 2  │   │  ENGINE 3    │   │ OPTIMIZER  ││
 │  Impact      │   │  What-If   │   │  Risk        │   │ Patrol     ││
 │  Predictor   │   │  Simulator │   │  Forecaster  │   │ Scheduler  ││
 │              │   │            │   │              │   │            ││
 │ GBM-36D     │   │ Counter-   │   │ HistGBM     │   │ Greedy     ││
 │ r=0.59      │   │ factual    │   │ r=0.92      │   │ Allocation ││
 │             │   │ 12 scenarios│   │ 27 models   │   │ 53× lift   ││
 └──────┬───────┘   └─────┬──────┘   └──────┬───────┘   └─────┬──────┘│
        │                 │                  │                 │       │
        │    Impact(road) │ Δ(road)          │ P(viol|road,h)  │       │
        └────────────┐    │    ┌─────────────┘                 │       │
                     ▼    ▼    ▼                               │       │
              ┌──────────────────────┐                         │       │
              │  Expected ROI Matrix │◄────────────────────────┘       │
              │  = P × Impact × Δ   │                                 │
              │  roads × 24 hours    │                                 │
              └──────────┬───────────┘                                 │
                         ▼                                             │
              ┌──────────────────────┐                                 │
              │  OPTIMAL SCHEDULE    │                                 │
              │  "Officer 3 → Outer  │                                 │
              │   Ring Rd, 8-10 AM"  │                                 │
              └──────────────────────┘                                 │
                          │                                             │
 ┌────────────────────────┴─────────────────────────────────────────────┤
 │                      DATA FOUNDATION                                │
 ├──────────────────┬──────────────────┬────────────────────────────────┤
 │  298K Violations │  393K Road Segs  │  Digital Twin Simulation      │
 │  87 features     │  OSM GraphML     │  Frank-Wolfe UE · BPR · 80z  │
 └──────────────────┴──────────────────┴────────────────────────────────┘
                          │
                          ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                   PRODUCTION STACK                                   │
 ├────────────────────────────┬─────────────────────────────────────────┤
 │  FastAPI Backend (:8000)   │  Next.js Dashboard (:3001)             │
 │  • Loads all models at     │  • 6 interactive pages                 │
 │    startup (in-memory)     │  • Leaflet maps with line geometry     │
 │  • Live inference on       │  • Animated gauges & counters          │
 │    every API call          │  • React Query for caching             │
 │  • 11 REST endpoints       │  • OLED-dark theme                     │
 │  • ~200ms per what-if      │  • Guided onboarding tutorial          │
 └────────────────────────────┴─────────────────────────────────────────┘
```

---

## Dashboard Pages

| Page | URL | Features |
|------|-----|----------|
| **Overview** | `/` | Animated KPIs, Pareto donut, hourly sparklines, division performance cards, top roads table, system status pills |
| **Impact Map** | `/map` | 393K road segments as polylines, 3 lens modes (Impact/Patrol/Risk), clickable segment detail panel with PIS breakdown, impact severity filter legend, patrol configuration (proportional & custom per-station) |
| **What-If Simulator** | `/whatif` | Road selector + scenario cards, station constraint dropdown, propagation map with polygon area selection, animated reduction gauge, cost-benefit ROI, network propagation rings |
| **Station Explorer** | `/stations` | 54 police stations with division filters (E/W/N/S), station cards with violations/risk/roads KPIs, Leaflet boundary map with colored polygons, drill-down panel with hourly trends and jurisdiction map |
| **Cluster Explorer** | `/clusters` | Bubble map of 1,087 HDBSCAN clusters, left panel with top hotspots ranked by severity, click-to-drill-down panel with road breakdown, hourly profile, vehicle types, "Enforce This Cluster" → What-If bridge |
| **Insights** | `/insights` | 8 live data-driven findings with hero metrics & evidence links, data quality scorecard, ML experiment log (8 models), methodology pipeline diagram |

All pages include a **guided onboarding tutorial** (powered by react-joyride) that auto-plays on first visit and can be replayed via the sidebar "Show Tutorial" button.

---

## API Endpoints

All endpoints are live — models are loaded into memory at startup and compute results on demand.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/overview` | System-wide KPIs: violations, segments, impact, cost, hourly distribution |
| `GET` | `/api/segments` | Bbox query with impact/tier filter, returns segments with line geometry (`lat_u/lon_u → lat_v/lon_v`) |
| `GET` | `/api/segment/{id}` | Full segment detail: PIS breakdown, hourly profile, neighbors |
| `POST` | `/api/whatif` | Live GBM re-prediction: zero violation features → compute delta. Returns propagation rings (hop 0/1/2) + cost-benefit ROI |
| `GET` | `/api/whatif/roads` | Searchable road names for the selector |
| `GET` | `/api/whatif/scenarios` | 12 predefined scenario results |
| `GET` | `/api/risk?hour=9` | Top risky segments for a given hour (normalized 0-1) |
| `GET` | `/api/risk/animation` | 24-hour risk animation data |
| `POST` | `/api/optimize` | Greedy patrol allocation for N officers |
| `GET` | `/api/stations` | List all stations with KPIs (violations, mean risk, roads), optional division filter |
| `GET` | `/api/clusters` | Top clusters with spatial bbox + radius |
| `GET` | `/api/cluster/{id}` | Cluster drill-down: road breakdown, hourly profile, vehicle types |
| `GET` | `/api/clusters/{id}/violations` | Raw violations in a cluster |
| `GET` | `/api/insights` | 8 live-computed findings + data quality scorecard + experiment log |
| `GET` | `/api/violations` | Search/filter raw violations |
| `GET` | `/health` | Health check |

---

## Key Results

### Engine 1 — Impact Prediction
| Metric | Value |
|--------|-------|
| Model | GBM-36D (Gradient Boosted Trees) |
| Test Spearman r | **0.59** |
| Top-1K precision | **45.2%** (subgraph) |
| #1 feature | `betweenness × tier` (37% importance) |
| Segments scored | 393,717 |

### Engine 2 — Counterfactual What-If (12 scenarios)
| Scenario | Violations Removed | Impact Reduction | Cost-Efficiency |
|----------|-------------------|-----------------|-----------------|
| 🏆 **Evening peak enforcement** | 2,403 (0.8%) | **4.1%** | **21× best** |
| Remove all cars | 88,868 (29.8%) | 7.2% | baseline |
| Repeat offenders (11+) | 8,385 (2.8%) | 3.8% | 5.6× |
| Top 50 roads | 127,010 (42.6%) | 2.0% | low |

### Engine 3 — Risk Forecaster (27 experiments)
| Metric | Value |
|--------|-------|
| Best model | HistGBM (historical + interactions, 16 features) |
| Test Spearman r | **0.9211** |
| Test R² | **0.998** |
| Models tested | GBM, XGBoost, LightGBM, RF, ExtraTrees, MLP, Ridge |
| Experiments | 27 (model types + feature ablation + combos + blending) |

### Enforcement Optimizer
| Fleet Size | Roads Covered | Lift over Random | Marginal ROI |
|-----------|--------------|-----------------|-------------|
| **10 officers** | 8 | **53.3×** | — |
| 50 officers | 39 | 37.6× | 1.06 |
| 200 officers | 104 | 23.5× | 0.50 |

---

## Novel Contributions

### 1. Per-Violation Impact Quantification
Most systems ask "is there a violation?" (binary). We compute a **continuous
impact score (PIS 0-100)** based on road geometry (IRC standards), network
position (betweenness centrality), and temporal context.

### 2. Three-Engine Closed Loop
The three engines aren't independent — they **feed each other**:
- Engine 3 predicts WHERE/WHEN → Engine 1 estimates HOW MUCH → Engine 2 computes WHAT IF → Optimizer allocates officers
- This is **predictive proactive enforcement**, not reactive catch-and-fine

### 3. The Enforcement Data Bias Discovery
Our optimizer revealed a **cold-start problem** in enforcement data:

```
The data says: "Few violations at 4-8 PM"
Reality:       "Few OFFICERS at 4-8 PM → fewer catches"
Naive AI:      Deploys ZERO officers at 4-8 PM (reinforcing the gap)
DRISHTAM:      Detects and flags this bias
```

Historical enforcement data only reflects **where you looked**, not where
violations actually occur. Any city deploying data-driven enforcement must
account for this — we are the first to formally identify and document it.

### 4. Digital Twin Traffic Simulation
Frank-Wolfe User Equilibrium traffic assignment on the full OSM road network
(393K segments, 155K nodes, 80 zones) reveals that parking violations add
**2M extra vehicle-hours per day** to Bengaluru's traffic.

### 5. Network-Aware Propagation Visualization
The What-If engine doesn't just show "impact reduced." It computes and returns **propagation rings** — showing how enforcement cascades from directly enforced roads (Hop 0) through nearby segments (Hop 1, within 500m) to ripple effects (Hop 2). This is rendered as an interactive propagation map.

---

## Assumptions & Limitations

| Assumption | Justification | Risk |
|-----------|--------------|------|
| Violations are uniformly reported by Astram cameras | Camera placement biases toward major roads | Minor roads may be underrepresented |
| Road capacity follows IRC (Indian Roads Congress) standards | Standard engineering reference | Actual capacity varies with conditions |
| BPR volume-delay function is appropriate | Industry standard for macroscopic models | Doesn't capture signal timing or lane-level effects |
| Historical violation patterns predict future violations | Parking is habitual (same roads, similar times) | Special events can disrupt patterns |
| Enforcement deters violations on targeted roads | Criminology literature on deterrence | Displacement effect: violators may shift to nearby roads |
| Vehicle width from IRC standards accurately estimates blockage | Conservative estimates | Actual parking angle affects true blockage |
| Peak hours (8-10 AM, 5-8 PM) are consistent | EDA confirms these peaks | Seasonal and event-driven variation exists |
| OSM road geometry is accurate for Bengaluru | OSM has strong coverage in Indian metros | Some roads may have outdated attributes |

---

## Data Pipeline

```
Raw Violations CSV (298K × 25)
        │
        ▼
┌─────────────────────────────┐
│ 01_build_enriched_data.py   │  ← Road matching, PIS scoring, temporal encoding
│ → violations_enriched.parquet│     HDBSCAN clustering, proximity features
│   (298K × 87 features)      │     87 engineered features
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 02_compute_impact_scores.py │  ← PIS computation, graph propagation
│ → propagated_impact.parquet │     GAT neural network training
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 03b_simulate_traffic.py     │  ← Frank-Wolfe UE, BPR functions
│ → simulation/baseline_flows │     80-zone OD matrix
│ → simulation/delay_metrics  │     6-hour simulation
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 03c_retrain_gnn_twin.py     │  ← GBM-36D training on sim labels
│ (run in Colab with GPU)     │     GPU betweenness centrality
│ → models/gbm_36d_best.pkl   │     Feature engineering + model sweep
│ → models/features_36d.npy   │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 04_train_forecaster.py      │  ← 27 model experiments
│ → risk_forecaster_best.pkl  │     Feature ablation + blending
│ → risk_predictions.parquet  │     Hourly risk maps
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 05_generate_counterfactuals │  ← 12 enforcement scenarios
│ → counterfactual_scenarios  │     Monotonicity verification
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 06_optimize_enforcement.py  │  ← Greedy officer allocation
│ → enforcement_schedule.json │     Fleet size comparison
│ → fleet_comparison.json     │     Hourly deployment heatmap
└─────────────────────────────┘
```

---

## Project Structure

```
DRISHTAM/
├── api/                                # FastAPI Backend (live inference)
│   ├── main.py                         # App entry: CORS, lifespan, router registration
│   ├── engine_loader.py                # Singleton EngineStore — loads all models at startup
│   ├── models.py                       # Pydantic schemas for all endpoints
│   └── routers/                        # REST endpoint handlers
│       ├── overview.py                 #   GET /api/overview
│       ├── segments.py                 #   GET /api/segments, /api/segment/{id}
│       ├── whatif.py                   #   POST /api/whatif (live GBM inference)
│       ├── risk.py                     #   GET /api/risk, /api/risk/animation
│       ├── optimizer.py                #   POST /api/optimize
│       ├── clusters.py                 #   GET /api/clusters, /api/cluster/{id}
│       ├── violations.py               #   GET /api/violations
│       └── insights.py                 #   GET /api/insights (live computed)
│
├── dashboard/                          # Next.js 15 Frontend
│   ├── src/app/                        # Pages (App Router)
│   │   ├── page.tsx                    #   / — Overview (KPIs, Pareto, sparklines)
│   │   ├── map/page.tsx                #   /map — Impact Map (3 lens modes)
│   │   ├── whatif/page.tsx             #   /whatif — What-If Simulator
│   │   ├── stations/page.tsx           #   /stations — Station Explorer
│   │   ├── clusters/page.tsx           #   /clusters — Cluster Explorer
│   │   ├── insights/page.tsx           #   /insights — Executive Insights
│   │   ├── layout.tsx                  #   Root layout (sidebar + query provider)
│   │   └── globals.css                 #   OLED-dark design system
│   ├── src/components/
│   │   ├── Layout/
│   │   │   ├── Sidebar.tsx             #   Navigation sidebar (6 pages + tutorial btn)
│   │   │   └── QueryProvider.tsx       #   React Query wrapper
│   │   ├── Map/
│   │   │   ├── SegmentMap.tsx          #   Leaflet map with polyline rendering
│   │   │   ├── SegmentPanel.tsx        #   Slide-in segment detail panel
│   │   │   ├── PropagationMap.tsx       #   What-If propagation visualization
│   │   │   ├── ClusterBubbleMap.tsx    #   Cluster bubble visualization
│   │   │   └── ClusterPanel.tsx        #   Cluster drill-down panel
│   │   ├── Stations/
│   │   │   ├── StationBoundaryMap.tsx  #   Leaflet map with Voronoi boundary polygons
│   │   │   └── StationPanel.tsx       #   Station drill-down overlay panel
│   │   ├── Tutorial/
│   │   │   ├── TutorialManager.tsx     #   Global Joyride orchestrator (react-joyride v3)
│   │   │   └── steps.ts               #   Per-page tutorial step definitions
│   │   ├── Charts/
│   │   │   ├── ParetoDonut.tsx         #   80/20 donut chart
│   │   │   ├── HourlyChart.tsx         #   24-hour bar chart
│   │   │   ├── Sparkline.tsx           #   Inline sparkline
│   │   │   └── TopRoadsTable.tsx       #   Top roads ranking table
│   │   ├── AnimatedCounter.tsx         #   Counting animation
│   │   ├── ReductionGauge.tsx          #   Circular reduction gauge
│   │   └── MiniMapPulse.tsx            #   Pulsing map thumbnail
│   └── src/lib/
│       ├── api.ts                      #   API client (typed fetch wrappers)
│       └── colors.ts                   #   Color utilities & formatters
│
├── drishtam/                           # Core ML Package (15 modules)
│   ├── config.py                       # Central configuration (IRC standards, BPR params)
│   ├── data_pipeline.py                # Phase 1: data loading & enrichment
│   ├── impact_scorer.py                # Engine 1: PIS computation
│   ├── graph_builder.py                # OSM → PyTorch Geometric graph
│   ├── propagation_model.py            # Engine 1b: GAT propagation
│   ├── traffic_simulator.py            # Digital twin: Frank-Wolfe UE
│   ├── traffic_zones.py                # 80 Bengaluru landmark zones + demand
│   ├── counterfactual.py               # Engine 2: what-if simulator
│   ├── risk_forecaster.py              # Engine 3: risk prediction (27 experiments)
│   ├── enforcement_optimizer.py        # Optimizer: patrol scheduling
│   ├── clustering.py                   # HDBSCAN hotspot detection
│   ├── verification.py                 # Data quality gates
│   ├── exceptions.py                   # Custom exception hierarchy
│   └── utils.py                        # Shared utilities
│
├── scripts/                            # Executable pipeline (run in order)
│   ├── 01_build_enriched_data.py       # Enrichment pipeline
│   ├── 02_compute_impact_scores.py     # Impact scoring
│   ├── 03_build_gnn_graph.py           # Graph construction
│   ├── 03b_simulate_traffic.py         # Digital twin simulation
│   ├── 03c_retrain_gnn_twin.py         # GBM training (Colab GPU)
│   ├── 04_train_forecaster.py          # Risk model sweep
│   ├── 05_generate_counterfactuals.py  # 12 scenarios
│   └── 06_optimize_enforcement.py      # Patrol optimization
│
├── research/                           # 11 reports + 96 visualizations
├── data/                               # Data files (not in git)
│   ├── violations_enriched.parquet     # 298K × 87
│   ├── bengaluru_roads.graphml         # 393K segments
│   ├── propagated_impact.parquet       # Impact propagation
│   ├── risk_predictions.parquet        # 344K hourly predictions
│   ├── counterfactual_scenarios.json   # 12 scenarios
│   ├── enforcement_schedule.json       # Optimal patrol schedule
│   ├── fleet_comparison.json           # Fleet ROI comparison
│   └── simulation/                     # Digital twin outputs
├── models/                             # Trained models (not in git)
│   ├── gbm_36d_best.pkl                # Engine 1 (5.7 MB)
│   ├── feature_scaler.pkl              # StandardScaler for 36 features
│   ├── risk_forecaster_best.pkl        # Engine 3 (521 KB)
│   ├── features_36d.npy                # Feature matrix (57 MB)
│   ├── segment_predictions.parquet     # All segments with geometry (34 MB)
│   └── ml_summary.json                 # Model metadata
├── archive/                            # Historical notebooks, EDA scripts, raw data
├── Dockerfile.api                      # API container
├── docker-compose.yml                  # Multi-service orchestration
├── pyproject.toml                      # Python project config
├── requirements.txt                    # Python dependencies
└── .env.example                        # Environment variable template
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Data files placed in `data/` and `models/` directories

### 1. Backend (FastAPI)
```bash
cd "Gridlock project"
python -m venv .venv
.venv\Scripts\Activate.ps1    # Windows
pip install -e ".[dev]"

# Start API server (loads all models, ~15s startup)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 2. Frontend (Next.js)
```bash
cd dashboard
npm install
npm run dev    # → http://localhost:3001
```

### 3. ML Pipeline (run once to generate data files)
```bash
python scripts/01_build_enriched_data.py
python scripts/02_compute_impact_scores.py
python scripts/03b_simulate_traffic.py

# Phase 3 (requires GPU — run in Colab)
# Upload scripts/03c_retrain_gnn_twin.py to Colab
# Download models/ to local

python scripts/04_train_forecaster.py        # 27 model experiments
python scripts/05_generate_counterfactuals.py  # 12 scenarios
python scripts/06_optimize_enforcement.py    # Patrol optimization
```

### Docker (Production)
```bash
docker-compose up --build
# API → :8000, Dashboard → :3001
```

---

## Research & EDA

| # | Report | Key Finding |
|---|--------|-------------|
| 01 | [Violation EDA](research/01_violation_eda.md) | 298K violations, enforcement gap 3:30-8:30 PM |
| 02 | [Event EDA](research/02_event_eda.md) | 8,057 events, 60.6% vehicle breakdowns |
| 03 | [Cross-Dataset](research/03_cross_dataset_analysis.md) | Spearman r=0.41 spatial correlation |
| 04 | [Road Network](research/04_osm_road_network.md) | 393K segments, link roads 2-4× violation density |
| 05 | [Research Landscape](research/05_research_landscape.md) | Literature review & gap analysis |
| 06 | [Enriched Data](research/06_enriched_data_summary.md) | 87 engineered features |
| 07 | [PIS Scores](research/07_parking_impact_scores.md) | Pareto: 13.8% cause 80% impact |
| 08 | [GNN Propagation](research/08_gnn_propagation.md) | MLP r=0.59 >> GNN r=0.24 |
| 09 | [Digital Twin](research/09_digital_twin_simulation.md) | 2M extra vehicle-hours/day |
| 10 | [GNN Retraining](research/10_gnn_twin_retraining.md) | GBM r=0.59, subgraph Top-1K 45% |
| 11 | [Phase 4 Results](research/11_counterfactuals_and_forecasting.md) | Risk r=0.92, 53× lift, data bias discovery |

---

## The Story

1. **Bengaluru has 298,000 parking violations** recorded by Astram cameras over 5 months. Every one gets a ₹500 fine. All treated equally.

2. **But a car on a 6-meter street blocks 33% of the road. On a 14-meter road, just 14%.** We compute a **Parking Impact Score (PIS)** that captures this — and find that **13.8% of violations cause 80% of congestion impact** (Pareto principle).

3. **Violations cascade.** A blocked arterial forces traffic onto side streets, which then overflow. Our **Digital Twin** — a macroscopic traffic simulation on 393K OSM road segments — shows violations add **2 million extra vehicle-hours per day** to Bengaluru's traffic. That's roughly **₹60 crore/day** in wasted time and fuel.

4. **We can predict which roads will have violations at each hour** with r=0.92 accuracy. And we can simulate "what if we enforce this road?" — finding that enforcing just the **evening peak gap (3:30-8:30 PM)** with 0.8% of total enforcement effort yields **4.1% congestion reduction** — the single most cost-effective intervention.

5. **The three engines combine into a Predictive Enforcement Optimizer** that tells the police: "Send Officer 3 to Outer Ring Road at 8 AM, then Service Road at 10 AM." Even **10 officers deployed this way outperform 530 randomly deployed officers** (53× lift).

6. **We discovered a critical data bias**: historical enforcement data only reflects *where you looked*, not where violations actually occur. The 4-8 PM "enforcement gap" means the AI has a blind spot exactly when congestion is worst. Any city deploying data-driven enforcement must account for this — **DRISHTAM is the first system to formally identify and flag it**.

7. **The dashboard makes it real.** A police commander can open the Impact Map, see the worst corridors rendered as glowing polylines, click a segment to see its full breakdown, draw a polygon to select an area, and run a What-If simulation that computes propagation rings showing how enforcement cascades through the road network — all backed by live model inference, not static JSON.

---

<div align="center">

**DRISHTAM** — *Revealing the invisible cost of illegal parking.*

*Built for Bengaluru. Designed for any city.*

**10 officers. 53× impact. One AI.**

</div>
