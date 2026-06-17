# Research #5: Literature & Research Landscape — Parking-Induced Congestion AI

> **Date**: June 17, 2026  
> **Purpose**: Log everything we found during research to inform solution design  
> **Status**: Complete — ready for Phase 1 implementation

---

## 1. Problem Statement

**Poor Visibility on Parking-Induced Congestion**

On-street illegal parking and spillover parking near commercial areas, metro stations, and events choke carriageways and intersections. Enforcement is patrol-based and reactive. No heatmap of parking violations vs. congestion impact exists. Difficult to prioritize enforcement zones.

**Core Question**: How can AI-driven parking intelligence detect illegal parking hotspots and **quantify their impact on traffic flow** to enable targeted enforcement?

---

## 2. Our Data Assets

| Dataset | Records | Key Fields | Status |
|---|---|---|---|
| **Parking Violations** | 298,445 | lat/lon, vehicle_type, violation_type, police_station, junction, datetime, validation_status | ✅ Fully explored (EDA #1) |
| **Traffic Events** | 8,057 | lat/lon, cause, planned/unplanned, severity, corridor, datetime, resolution | ✅ Fully explored (EDA #2) |
| **OSM Road Network** | 393,717 segments | geometry, highway_type, lanes, width, name, length | ✅ Fully explored (EDA #4) |
| **Cross-Dataset** | — | Grid correlation, proximity analysis, quintile gradients | ✅ Fully explored (EDA #3) |

---

## 3. Key EDA Findings That Drive Our Solution

### From EDA #1 (Violations — 01_violation_eda.md):
1. **55.3% are "WRONG PARKING", 46.6% "NO PARKING"** — dominant types
2. **10.1% (30,070) are directly congestion-relevant** (main road, double, near crossing, near bustop)
3. **Evening rush (3:30-8:30 PM IST) has near-zero enforcement** — the #1 actionable gap
4. **Top 5 junctions = 32% of tagged violations** (Safina Plaza, KR Market, Elite, Sagar Theatre)
5. **46.2% are two-wheelers** (low physical impact) vs **29.8% cars** (high impact) — weight by vehicle size
6. **28.7% rejection rate** on validation — quality issue to account for
7. **552 vehicles have 11+ violations** — repeat offender targeting opportunity
8. **Zero enforcement follow-through data** (closed_datetime, action_taken are 100% empty)

### From EDA #2 (Events — 02_event_eda.md):
1. **60.6% vehicle breakdowns**, 95.5% unplanned events
2. **Bimodal hourly pattern** matching violation pattern (r=0.824 hourly correlation)
3. **BMTC buses = 30% of breakdowns** — public transport reliability issue
4. **Mysore Road is #1 corridor** for events
5. Events cluster on **arterial roads and ORR junctions** (different spatial niche from violations)

### From EDA #3 (Cross-Dataset — 03_cross_dataset_analysis.md):
1. **Spearman r=0.409** (p<10⁻⁶⁹) — moderate-strong spatial correlation at 500m grid
2. **10× quintile gradient** — cells in highest violation quintile have 10× more events
3. **3.0× zone ratio** — high-violation zones have 3× more events per cell
4. **Daily temporal: NOT correlated** (r=0.02) — violations are a persistent spatial problem
5. **95.6% of events within 300m of a violation** — near-universal co-occurrence
6. **SURPRISE: Congestion events have FEWER nearby violations** — different spatial niches
7. **HAL Old Airport** = only station ranking high in BOTH violations (#4) and events (#2)
8. **Bottom line**: Correlation is driven by urban density (confounding), not direct causation

### From EDA #4 (OSM Roads — 04_osm_road_network.md):
1. **81.8% of road network is residential**, only **2.9% is primary/arterial/motorway**
2. **32.6% of violations on tertiary roads**, 23.8% residential, 16.4% secondary
3. **Link roads (ramps/connectors) have 2-4× higher violation density** than parent roads — CRITICAL
4. **75.7% of violations on 2-lane roads** — one car = 50% lane blockage
5. **Mean road width blocked: 16.4%**, 41,236 violations (13.8%) block >25%
6. **BSF STS Road**: #1 hotspot with 5,231 violations, impact score 4× #2
7. **Tertiary ramps median 40% blocked, living streets 37.5%** — most vulnerable
8. Violations cluster at **commercial intersections, market areas, junction connectors**

---

## 4. Existing Approaches in Literature

### Category A: Detection-Focused Systems
- **YOLO-based detection** (YOLOv5/v8/SSD/Faster R-CNN) on CCTV feeds
- **ALPR + OCR** for automated fine issuing
- **Edge AI** (Raspberry Pi, Jetson Nano) for real-time monitoring
- **Polygon-based zone monitoring** (define no-park zones, flag intrusions)

**Gap**: All answer "IS there illegal parking?" — none quantify "HOW MUCH does it hurt traffic?"

### Category B: Simulation-Based Impact Studies
- **VISSIM/SUMO microsimulation** — model blockages as incidents, measure delay
- **Highway Capacity Manual (HCM)** friction factors for on-street parking
- **Net Road Width (NRW)** calculation via GIS + video

**Key findings from literature**:
- Illegal parking reduces capacity by **20-50%** depending on severity
- Link delays increase up to **50%** in high-traffic scenarios
- Double parking is the most impactful form

**Gap**: These are academic exercises on synthetic networks. Nobody applied this to real violation records at city scale with actual road geometry from OSM.

### Category C: Prediction Models
- **LSTM/RNN** for time-series violation/congestion prediction
- **Graph Neural Networks (GNN)** for traffic flow prediction on road networks
- **Spatio-Temporal GCN (STGCN)** with dynamic adjacency matrices
- **Semi-supervised GCN** for parking violation rate prediction (2024)
- **CAP-STGCN** (2024) — physics-guided GCN for congestion prediction
- **XGBoost/Random Forest** for spatiotemporal classification

**Gap**: Predict violations OR congestion separately. Nobody predicts violation IMPACT as a composite.

### Category D: Enforcement Optimization
- **Deep Reinforcement Learning (DRL)** — MDP-based patrol routing
- **Multi-Agent RL (MARL)** — coordinate multiple patrol units
- **Integer Linear Programming** — fixed schedule optimization

**Gap**: Assumes you know WHERE to enforce. The upstream question "which violations matter most?" is unanswered.

### Category E: Digital Twins
- **Bengaluru Mobility Digital Twin** — ₹1 crore project by BTP
- **ASTraM platform** — existing traffic management
- **87% of violations** detected by AI cameras in Bengaluru (2025)

**Gap**: Macro-level planning tools without violation-level impact scoring.

---

## 5. Existing Systems in Bengaluru

| System | What It Does | Our Relationship |
|---|---|---|
| **ITeMS** (Intelligent Traffic Management System) | Signal management, camera monitoring | We provide the violation-impact layer they lack |
| **ASTraM** | Traffic event management | Our event data comes from here |
| **AI Cameras (87% detection)** | Automated violation detection | Our violation data comes from these |
| **Mobility Digital Twin (planned)** | City-level simulation | We provide micro-level violation scoring |

---

## 6. Relevant Academic Papers

| Paper / Approach | Year | Key Contribution | How We Build On It |
|---|---|---|---|
| CAP-STGCN (MDPI) | 2024 | Physics-guided GCN for congestion forecasting | We add violation-as-perturbation to graph |
| Semi-supervised GCN for violation prediction (ResearchGate) | 2024 | Predicts violation rates using graph | We go beyond prediction → impact scoring |
| VISSIM illegal parking simulation (U of Toronto) | 2023 | Microsimulation: 20-50% capacity loss | We validate with REAL data at city scale |
| Behavior-Aware Hypergraph CNN | 2024 | Multi-relational graph for parking | Inspiration for graph structure |
| STGNPP (arXiv) | 2024 | Congestion propagation as point process | Direct inspiration for propagation model |
| Toronto Congestion Impact Score | 2024 | Weighted: severity × extent × duration × importance | Our PIS formula follows similar philosophy |
| Bengaluru MDT (Hiverlab/BTP) | 2025 | City-level traffic simulation | We provide the missing violation-impact layer |

---

## 7. The Novelty — What Nobody Has Done

| Dimension | State of Art | ParkImpact (Ours) |
|---|---|---|
| **Detection** | "Is there a violation?" (binary) | We don't detect — we already have 298K records |
| **Impact** | "Violations cause congestion" (qualitative) | **"This violation blocks 34.6% of road width, PIS=83/100"** |
| **Granularity** | City-level or zone-level | **Per-violation, per-road-segment** |
| **Road context** | Ignored or generic | **OSM geometry: lanes, width, type, junction proximity** |
| **Network effects** | Not modeled | **GAT-based propagation on real road graph** |
| **Prioritization** | By violation count | **By congestion IMPACT score** |
| **What-if** | Not available | **"Remove Road X → Y% reduction"** counterfactuals |
| **Temporal** | Static or real-time only | **Predictive — where will high-impact violations occur next?** |
| **Visualization** | Basic heatmaps | **Interactive impact maps, propagation animations, what-if simulator** |

---

## 8. MapMyIndia / Mappls Consideration

**MapMyIndia (Mappls)** offers India-specific map data that may be more detailed than OSM for Indian roads:
- **Richer road metadata**: Dividers, service roads, speed limits, one-way tags
- **Points of Interest**: Metro stations, bus stops, markets — useful for contextual features
- **Traffic APIs**: Real-time and historical traffic data (if available)
- **Geocoding**: More accurate for Indian addresses

**Decision**: We will use **OSM as primary** (we already have the 393K segment graph), but investigate MapMyIndia/Mappls APIs for:
1. POI data (metro stations, bus stops, commercial areas) for contextual features
2. Real-time traffic overlays for dashboard
3. Map tiles for the dashboard (may look better than OSM tiles for India)

---

## 9. Solution Architecture Decision

**ParkImpact: Unified Three-Engine AI Platform**

- **ENGINE 1**: Parking Impact Score (PIS) — per-violation, 0-100 scale
- **ENGINE 1b**: Graph Attention Network (GAT) propagation on road network
- **ENGINE 2**: Counterfactual What-If Engine — scenario-based impact estimation
- **ENGINE 3**: Spatio-temporal Risk Forecaster — predict future high-impact violations

**Tech Stack**:
- ML: PyTorch, PyTorch Geometric, scikit-learn, XGBoost, LightGBM, SHAP
- Data: pandas, geopandas, OSMnx, scipy, HDBSCAN
- Backend: FastAPI
- Frontend: Next.js + Leaflet.js (consider MapMyIndia tiles)
- Deployment: Cloud with GPU support

---

## 10. Key Design Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| GNN vs Heuristic propagation | **Full GNN (GAT)** | Time is available, GNN is more impressive and novel |
| Causal claims | **Model-based estimates with CI** | Cannot run real experiments |
| Map provider | **OSM primary + MapMyIndia for tiles/POI** | OSM already downloaded; MapMyIndia for Indian detail |
| Deployment | **Cloud (GPU available)** | Both local GPU (RTX 2050) and cloud credits available |
| Visualization priority | **HIGHEST** | "Visualization is the key" — every output must be visual |
| train.csv | **Removed** | Not relevant to our project |
