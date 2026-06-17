<div align="center">

# दृष्टम् — DRISHTAM

### *"That which has been revealed."*

**Data-driven Road Impact Scoring for Traffic Hotspot Analysis & Management**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.2+-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14+-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)

---

*Every day, 298,000 parking violations choke Bengaluru's roads.*  
*But not all violations are equal.*  
*A car on a 6-meter street blocks 33% of capacity.*  
*The same car on a 14-meter road blocks just 14%.*

**DRISHTAM reveals what nobody could see — the invisible cost of every illegally parked vehicle.**

</div>

---

## The Problem

On-street illegal parking and spillover parking near commercial areas, metro stations, and events choke carriageways and intersections. Enforcement is patrol-based and reactive. No system quantifies which violations actually matter.

**The gap**: Current systems detect violations (binary: yes/no). Nobody measures *how much* each violation hurts traffic flow.

## The Solution

DRISHTAM is the **first AI system** to score every parking violation's congestion impact, model how that impact propagates through the road network, and predict where tomorrow's worst violations will occur.

### Three Engines, One Platform

```
┌──────────────────────────────────────────────────────────────────┐
│                          DRISHTAM                                │
│               दृष्टम् — "That which has been revealed"           │
├──────────────┬────────────────────┬──────────────────────────────┤
│  ENGINE 1    │     ENGINE 2       │         ENGINE 3             │
│  Impact      │   What-If          │     Risk Forecast            │
│  Scorer      │   Simulator        │                              │
├──────────────┼────────────────────┼──────────────────────────────┤
│ Per-violation │ "Remove top-50    │ "Tomorrow 10 AM,             │
│ score 0-100  │  roads → X%       │  MG Road: Risk=87            │
│ + GNN prop-  │  congestion       │  because P(viol)=0.94        │
│   agation    │  reduction"       │  × Impact=92"                │
├──────────────┴────────────────────┴──────────────────────────────┤
│              OSM Road Graph  ·  298K Violations  ·  8K Events    │
├──────────────────────────────────────────────────────────────────┤
│         FastAPI Backend  ·  Next.js Interactive Dashboard         │
└──────────────────────────────────────────────────────────────────┘
```

| Engine | What It Does | ML Core |
|---|---|---|
| **Impact Scorer** | Scores every violation 0-100 based on road geometry, network position, and time | Parking Impact Score (PIS) formula + Graph Attention Network propagation |
| **What-If Simulator** | "If we enforce Road X, congestion drops by Y%" | Counterfactual estimation via graph re-computation |
| **Risk Forecaster** | Predicts where high-impact violations will occur next | XGBoost/LightGBM ensemble + SHAP explainability |

## Key Findings

| Finding | Value | Implication |
|---|---|---|
| 🔴 **13.8% of violations cause ~80% of impact** | 41,236 / 298,445 | Targeted enforcement, not blanket coverage |
| 🔴 **Evening rush has ZERO enforcement** | 3:30-8:30 PM IST | Biggest gap when congestion is worst |
| 🟠 **75.7% of violations on 2-lane roads** | 1 car = 50% blockage | Narrow roads bear disproportionate burden |
| 🟠 **Link roads have 2-4× violation density** | Junction connectors | Most vulnerable network chokepoints |
| 🟢 **BSF STS Road = #1 impact hotspot** | 4× higher than #2 | One camera here saves thousands of congestion-hours |

## Tech Stack

| Layer | Technology |
|---|---|
| **ML Pipeline** | PyTorch, PyTorch Geometric (GAT), XGBoost, LightGBM, SHAP |
| **Data** | pandas, geopandas, OSMnx, scipy, HDBSCAN |
| **Backend** | FastAPI, Pydantic, uvicorn |
| **Frontend** | Next.js 14, Leaflet.js, Recharts, Framer Motion |
| **Maps** | OpenStreetMap (road network) + MapMyIndia (tiles) |
| **Quality** | Ruff (lint+format), Mypy (types), Bandit (security), Pytest (60%+ coverage) |

## Project Structure

```
DRISHTAM/
├── drishtam/                    # Core ML package
│   ├── config.py                # Central configuration
│   ├── data_pipeline.py         # Data loading & enrichment
│   ├── impact_scorer.py         # ENGINE 1: PIS computation
│   ├── graph_builder.py         # OSM → PyTorch Geometric graph
│   ├── propagation_model.py     # ENGINE 1b: GAT propagation
│   ├── counterfactual.py        # ENGINE 2: What-if simulator
│   ├── risk_forecaster.py       # ENGINE 3: Risk prediction
│   ├── clustering.py            # HDBSCAN hotspot detection
│   ├── exceptions.py            # Custom exception hierarchy
│   ├── verification.py          # Data quality gates
│   └── utils.py                 # Shared utilities
│
├── scripts/                     # Executable pipeline scripts
│   ├── 01_build_enriched_data.py
│   ├── 02_compute_impact_scores.py
│   ├── 03_build_road_graph.py
│   ├── 04_train_forecaster.py
│   ├── 05_generate_counterfactuals.py
│   ├── 06_export_for_dashboard.py
│   └── quality_check.py         # Run all code quality checks
│
├── api/                         # FastAPI backend
├── dashboard/                   # Next.js frontend
├── research/                    # EDA reports + visualizations (62 files)
├── plans/                       # Detailed 5-phase implementation plans
├── data/                        # Data files (not in git)
├── tests/                       # Test suite
└── pyproject.toml               # Project config + tool settings
```

## Quick Start

```bash
# Clone
git clone https://github.com/SK8-infi/DRISHTAM.git
cd DRISHTAM

# Setup environment
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
pip install -e ".[dev]"

# Run quality checks
python scripts/quality_check.py

# Run the ML pipeline (after placing data files in data/)
python scripts/01_build_enriched_data.py
python scripts/02_compute_impact_scores.py
python scripts/03_build_road_graph.py
python scripts/04_train_forecaster.py
python scripts/05_generate_counterfactuals.py
python scripts/06_export_for_dashboard.py

# Start the dashboard
cd api && uvicorn main:app --reload     # Backend on :8000
cd dashboard && npm run dev             # Frontend on :3000
```

## Research & EDA

Comprehensive exploratory data analysis has been completed across 4 phases:

| Report | Records | Key Finding |
|---|---|---|
| [01 — Violation EDA](research/01_violation_eda.md) | 298,445 violations | Evening rush enforcement gap |
| [02 — Event EDA](research/02_event_eda.md) | 8,057 events | 60.6% vehicle breakdowns |
| [03 — Cross-Dataset](research/03_cross_dataset_analysis.md) | Combined | Spearman r=0.41 spatial correlation |
| [04 — Road Network](research/04_osm_road_network.md) | 393,717 segments | Link roads: 2-4× violation density |
| [05 — Research Landscape](research/05_research_landscape.md) | — | Literature review & gap analysis |

## Implementation Plan

The project follows a 5-phase execution plan with verification gates at every step:

| Phase | Focus | Plan |
|---|---|---|
| Phase 1 | Data Foundation & Enrichment | [phase1_data_foundation.md](plans/phase1_data_foundation.md) |
| Phase 2 | Impact Scoring (PIS) + Clustering | [phase2_impact_scoring.md](plans/phase2_impact_scoring.md) |
| Phase 3 | GNN Propagation (GAT) | [phase3_gnn_propagation.md](plans/phase3_gnn_propagation.md) |
| Phase 4 | What-If + Risk Forecasting | [phase4_whatif_and_forecasting.md](plans/phase4_whatif_and_forecasting.md) |
| Phase 5 | Dashboard + Deployment | [phase5_dashboard_and_deployment.md](plans/phase5_dashboard_and_deployment.md) |

## What Makes This Novel?

| Dimension | State of the Art | DRISHTAM |
|---|---|---|
| **Detection** | "Is there a violation?" (binary) | We already have 298K records — we go beyond detection |
| **Impact** | "Violations cause congestion" (qualitative) | **"This violation blocks 34.6% of road width, PIS=83/100"** |
| **Granularity** | City-level or zone-level | **Per-violation, per-road-segment** |
| **Network effects** | Not modeled | **GAT-based propagation on real road graph** |
| **What-if** | Not available | **Counterfactual scenario simulation** |
| **Temporal** | Static or real-time only | **Predictive — where will high-impact violations occur next?** |

---

<div align="center">

**DRISHTAM** — *Revealing the invisible cost of illegal parking.*

*Built for Bengaluru. Designed for any city.*

</div>
