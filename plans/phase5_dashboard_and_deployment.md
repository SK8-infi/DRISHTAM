# Phase 5: FastAPI Backend + Next.js Dashboard + Deployment

> **Goal**: Build a stunning, interactive dashboard that visualizes everything  
> **Inputs**: All outputs from Phases 1-4  
> **Outputs**: Deployed cloud application with full interactive dashboard  
> **Dependencies**: Phases 1-4 complete (can start scaffold with mock data earlier)

---

## 5.1 Data Export for Dashboard

### Step 5.1.1: Export Pipeline

```
File: scripts/06_export_for_dashboard.py
```

**Tasks**:
- [ ] Export violation GeoJSON: `violations.geojson` — each violation with lat/lon, PIS, PIS_band, road_name, violation_type, vehicle_type, hour_ist
- [ ] Export road segments GeoJSON: `road_segments.geojson` — each segment with geometry, propagated_impact, direct_pis, road_type, lanes, width
- [ ] Export clusters GeoJSON: `clusters.geojson` — cluster polygons (convex hulls) with stats
- [ ] Export scenario results: `scenarios.json` — pre-computed what-if results
- [ ] Export risk data: `risk_hourly.json` — per-hour risk maps (24 snapshots)
- [ ] Export alerts: `alerts.json` — current top-20 risk alerts
- [ ] Export summary stats: `summary.json` — city-wide KPIs
- [ ] Export SHAP data: `shap_summary.json` — feature importance for frontend charts
- [ ] Export temporal data: `temporal_patterns.json` — hourly/daily patterns for charts

**Size optimization**:
- [ ] Simplify geometries (reduce precision to 5 decimal places)
- [ ] Use MapBox Vector Tiles (MVT) for large datasets if >50MB
- [ ] Compress GeoJSON with property filtering (only include needed fields)

**Verification**:
- [ ] All GeoJSON files are valid (use `geojson-validation`)
- [ ] Total export size < 100MB (manageable for frontend)
- [ ] JSON files parse correctly

---

## 5.2 FastAPI Backend

### Step 5.2.1: Project Setup

```
File: api/main.py
```

**Tasks**:
- [ ] Initialize FastAPI app with metadata (title, description, version)
- [ ] Configure CORS (allow frontend origin)
- [ ] Add health check endpoint: `GET /api/health`
- [ ] Add lifespan handler: load data files on startup
- [ ] Add error handling middleware

### Step 5.2.2: Dashboard Summary Endpoints

```
File: api/routes/dashboard.py
```

| Endpoint | Response |
|---|---|
| `GET /api/dashboard/summary` | City-wide KPIs: total violations, mean PIS, critical count, top 5 hotspots, enforcement gap hours |
| `GET /api/dashboard/temporal` | Hourly/daily patterns for overview charts |
| `GET /api/dashboard/kpi-cards` | 6 KPI card data: violations, critical %, top road, enforcement gap, risk level, estimated capacity loss |

### Step 5.2.3: Impact Map Endpoints

```
File: api/routes/impact.py
```

| Endpoint | Response |
|---|---|
| `GET /api/impact/violations?bbox=...&pis_min=0&pis_max=100` | Filtered violation GeoJSON with PIS |
| `GET /api/impact/segments?bbox=...` | Road segments with propagated impact |
| `GET /api/impact/road/{road_name}` | Detailed per-road stats: violation count, mean/max PIS, temporal pattern, vehicle breakdown |
| `GET /api/impact/top?n=20&metric=pis` | Top N segments by PIS, count, or propagated impact |
| `GET /api/impact/propagation/{segment_id}` | Propagation cascade from a specific segment (for animation) |

### Step 5.2.4: What-If Endpoints

```
File: api/routes/whatif.py
```

| Endpoint | Response |
|---|---|
| `GET /api/whatif/scenarios` | List of pre-computed scenarios with results |
| `GET /api/whatif/scenario/{id}` | Detailed results for one scenario with affected segments |
| `POST /api/whatif/simulate` | Body: `{roads: ["BSF STS Road", ...]}` → real-time what-if result |
| `GET /api/whatif/compare?s1=1&s2=2` | Side-by-side comparison of two scenarios |

### Step 5.2.5: Forecast Endpoints

```
File: api/routes/forecast.py
```

| Endpoint | Response |
|---|---|
| `GET /api/forecast/risk?hour=10&day=monday` | Risk map GeoJSON for specified time |
| `GET /api/forecast/alerts?hour=10` | Top 20 risk alerts for specified time |
| `GET /api/forecast/24h` | All 24 hourly risk snapshots (for animation) |
| `GET /api/forecast/shap` | SHAP feature importance data |
| `GET /api/forecast/persistent-hotspots` | Segments that are high-risk at ALL hours |

### Step 5.2.6: Cluster Endpoints

```
File: api/routes/clusters.py
```

| Endpoint | Response |
|---|---|
| `GET /api/clusters` | All HDBSCAN clusters with stats |
| `GET /api/clusters/{id}` | Detailed cluster profile: roads, violations, temporal pattern, enforcement recommendation |
| `GET /api/clusters/enforcement-zones?n=20` | Top N enforcement priority zones |

**Verification**:
- [ ] All endpoints return valid JSON
- [ ] Response times < 500ms for pre-computed data
- [ ] `POST /api/whatif/simulate` returns in < 5 seconds
- [ ] Bbox filtering works correctly (only returns data in viewport)
- [ ] Error handling: invalid params return 400 with message

---

## 5.3 Next.js Dashboard

### Step 5.3.1: Project Setup

**Tasks**:
- [ ] Initialize Next.js project with App Router
- [ ] Install dependencies: `leaflet`, `react-leaflet`, `recharts` (charts), `framer-motion` (animations), `@tanstack/react-query` (data fetching)
- [ ] Set up global theme: dark mode with accent colors
- [ ] Create layout: sidebar navigation + main content area
- [ ] Set up API client (fetch wrapper)
- [ ] Consider MapMyIndia/Mappls tiles for map base layer

### Step 5.3.2: Design System

**Color palette**:
```
Background: #0a0f1a (deep navy)
Surface: #121a2e (elevated surface)
Card: #1a2340 (card background)
Border: #2a3558 (subtle borders)

Accent: #00d4ff (cyan — primary action)
Success: #00ff88 (green — low impact)
Warning: #ffaa00 (amber — moderate)
Danger: #ff4444 (red — high impact)
Critical: #cc00ff (purple — critical)

PIS Gradient: #00ff88 → #ffaa00 → #ff4444 → #cc00ff (0 → 100)
```

**Typography**: Inter (headings), JetBrains Mono (numbers/data)

**Design principles**:
- Dark mode ONLY — modern, data-dashboard feel
- Glassmorphism for cards (blur + transparency)
- Micro-animations on hover/interaction
- Data-dense but not cluttered
- Every number has context (comparison, trend indicator)

### Step 5.3.3: Pages

#### Page 1: Overview Dashboard (`/`)

**Layout**: 
```
┌─────────────────────────────────────────────────────────┐
│  🏙️ ParkImpact — Bengaluru Parking Intelligence         │
├──────┬──────┬──────┬──────┬──────┬──────────────────────┤
│ KPI  │ KPI  │ KPI  │ KPI  │ KPI  │  KPI                 │
│ Card │ Card │ Card │ Card │ Card │  Card                │
├──────┴──────┴──────┴──────┴──────┴──────────────────────┤
│                                    │ Top 10 Hotspots     │
│  Mini Bengaluru Map (impact       │ (ranked list with    │
│  heatmap, interactive)            │  PIS bars)           │
│                                    │                     │
├────────────────────────────────────┼─────────────────────┤
│  Temporal Pattern Chart            │ Impact Distribution  │
│  (hourly violations + PIS line)    │ (PIS histogram)     │
└────────────────────────────────────┴─────────────────────┘
```

**KPI Cards** (animated counters):
1. **298,445** — Total Violations Analyzed
2. **41,236 (13.8%)** — Critical Violations (>25% blockage)
3. **BSF STS Road** — #1 Impact Hotspot (PIS: XX)
4. **0 hours** — Evening Enforcement (the gap!)
5. **~40%** — Est. Impact Reduction (if top 50 roads enforced)
6. **87** — Live Risk Score (current hour)

#### Page 2: Impact Map (`/impact`)

**Layout**: Full-screen interactive map

**Features**:
- [ ] Leaflet map with dark tile layer (CartoDB Dark Matter or MapMyIndia dark)
- [ ] Toggle layers:
  - Violation points (colored by PIS, sized by capacity_blocked)
  - Road segments (colored by propagated impact)
  - Cluster boundaries (polygon overlays)
  - Heatmap mode (kernel density)
- [ ] Click on violation → popup with full details (PIS breakdown, road info, vehicle type)
- [ ] Click on road segment → popup with aggregated stats
- [ ] Filter panel (collapsible):
  - PIS range slider
  - Road type checkboxes
  - Vehicle type checkboxes
  - Time range slider
  - Violation type multi-select
- [ ] Legend: PIS gradient with band labels
- [ ] Mini chart in sidebar: PIS distribution of visible violations

**📊 Visualization requirements**:
- Smooth gradient rendering for PIS (no harsh color jumps)
- Cluster animations (pulse effect on hover)
- Road segment highlight on hover (thicken + glow)
- WebGL renderer for performance with 298K points

#### Page 3: Hotspot Explorer (`/hotspots`)

**Layout**:
```
┌──────────────────────────────────┬──────────────────────┐
│                                  │  Cluster Profile      │
│  Map with cluster polygons      │  Card (selected)      │
│  (colored by aggregate impact)   │                      │
│  Click to select                │  - Mean PIS: 67       │
│                                  │  - Violations: 3,241  │
│                                  │  - Road type: Tertiary│
│                                  │  - Peak: 9:30 AM IST  │
│                                  │  - Mini temporal chart │
│                                  │  - Vehicle breakdown   │
│                                  │  - Enforcement rec     │
├──────────────────────────────────┼──────────────────────┤
│  Cluster Ranking Table           │  Road Breakdown       │
│  (sortable by impact, count,     │  (per-road stats in   │
│   mean PIS, area)                │   selected cluster)   │
└──────────────────────────────────┴──────────────────────┘
```

**Features**:
- [ ] HDBSCAN clusters on map with convex hull polygons
- [ ] Color by aggregate impact (dark red = worst)
- [ ] Click cluster → detailed profile in sidebar
- [ ] Profile includes: mini temporal chart, vehicle pie, road type bar, enforcement recommendation
- [ ] "Generate Patrol Route" button (suggests optimal path through cluster)

#### Page 4: What-If Simulator (`/whatif`)

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  ⚙️ What-If Congestion Simulator                         │
├────────────────────────┬─────────────────────────────────┤
│                        │  BEFORE              AFTER      │
│  Select Roads to       │  ┌─────────┐  →    ┌─────────┐ │
│  Enforce:              │  │  Map 1   │       │  Map 2   │ │
│                        │  │ (current)│       │(scenario)│ │
│  □ BSF STS Road        │  └─────────┘       └─────────┘ │
│  □ GKVK Road           │                                │
│  □ KR Road             │  Impact Reduction:             │
│  □ [Search...]         │  ████████████░░ 42.3%          │
│                        │                                │
│  OR Pick Scenario:     │  Affected Segments: 1,234      │
│  ▼ [Top 50 Roads]      │  Capacity Restored: 12.4 km    │
│                        │                                │
│  [SIMULATE]            │  Pareto Chart:                  │
│                        │  (effort vs. reduction)         │
├────────────────────────┴─────────────────────────────────┤
│  Pre-computed Scenarios Comparison                        │
│  ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐    │
│  │ S1 │ S2 │ S3 │ S4 │ S5 │ S6 │ S7 │ S8 │ S9 │S10│    │
│  │15% │35% │25% │45% │ 3% │18% │50% │32% │20% │10%│    │
│  └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘    │
└──────────────────────────────────────────────────────────┘
```

**Features**:
- [ ] Road search/selection (autocomplete from known road names)
- [ ] Click roads on map to add/remove from scenario
- [ ] Pre-computed scenario dropdown
- [ ] "SIMULATE" button → calls API → before/after comparison
- [ ] Animated transition between before/after maps
- [ ] Impact reduction progress bar (animated fill)
- [ ] Scenario comparison cards at bottom (click to load)
- [ ] "Export Report" button → generates PDF summary

#### Page 5: Risk Forecast (`/forecast`)

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  🔮 Risk Forecast — When & Where Will Impact Be Highest? │
├──────────────────────────────────┬───────────────────────┤
│                                  │  ⚠️ Current Alerts    │
│  Map: Risk heatmap for           │  1. BSF STS Rd  [92] │
│  selected time                   │  2. KR Market   [87] │
│                                  │  3. Safina Plz  [84] │
│  ⏰ Time Slider:                 │  ...                 │
│  ◄── 12AM ───── NOW ───── 11PM ──►│                     │
│  [▶ PLAY 24H ANIMATION]          │  📊 SHAP Analysis    │
│                                  │  [View Explanations] │
├──────────────────────────────────┤                      │
│  Risk Clock (polar chart)        │  Feature Importance  │
│  Showing aggregate risk by hour  │  (interactive SHAP   │
│                                  │   beeswarm)          │
└──────────────────────────────────┴───────────────────────┘
```

**Features**:
- [ ] Time slider: drag to see risk map at any hour
- [ ] Play button: animate 24-hour cycle (smooth transitions)
- [ ] Current alerts panel (updates with time slider)
- [ ] Risk Clock: polar chart showing hourly aggregate risk
- [ ] SHAP modal: interactive feature importance visualization
- [ ] "Persistent vs Peak-Only" toggle on map
- [ ] Click segment → individual prediction explanation (SHAP waterfall)

#### Page 6: Propagation Viewer (`/propagation`)

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  🌊 Impact Propagation — How Violations Spread           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [Select a road segment or click on map]                 │
│                                                          │
│  ┌────────────────────────────────────────────────┐      │
│  │                                                │      │
│  │  Animated network visualization               │      │
│  │  Source: glowing red                           │      │
│  │  Hop 1: orange (impact × decay)               │      │
│  │  Hop 2: yellow (impact × decay²)              │      │
│  │  Hop 3: green (impact × decay³)               │      │
│  │                                                │      │
│  └────────────────────────────────────────────────┘      │
│                                                          │
│  Impact Decay Curve:    Attention Weights:                │
│  [Exponential chart]    [Which neighbors matter?]        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Features**:
- [ ] Click any road segment → animated propagation visualization
- [ ] Ripple animation: impact spreads outward from source
- [ ] Color coding: red → orange → yellow → green (decay visualization)
- [ ] Impact decay chart: shows how impact reduces at each hop
- [ ] Attention weight visualization: which neighbor connections carry most impact
- [ ] "The Hidden Victims" mode: highlight zero-violation segments receiving propagated impact

#### Page 7: Insights & Research (`/insights`)

**Layout**: Scrollable report page with embedded charts

**Features**:
- [ ] Auto-generated from research/ folder findings
- [ ] Interactive charts (hover for details)
- [ ] Key finding cards with "So What?" interpretations
- [ ] Data quality section
- [ ] Methodology explanation with diagrams
- [ ] References to academic papers

---

## 5.4 Deployment

### Step 5.4.1: Containerization

**Tasks**:
- [ ] Create `Dockerfile` for FastAPI backend (Python 3.13 + CUDA)
- [ ] Create `Dockerfile` for Next.js frontend
- [ ] Create `docker-compose.yml` for orchestration
- [ ] Include data volumes for model files and exported data

### Step 5.4.2: Cloud Deployment

**Tasks**:
- [ ] Deploy backend to cloud (AWS EC2 with GPU or GCP Compute Engine)
- [ ] Deploy frontend to Vercel or cloud VM
- [ ] Set up domain/subdomain
- [ ] Configure HTTPS
- [ ] Test all endpoints from deployed URL
- [ ] Load test: ensure 50 concurrent users don't crash it

**Verification**:
- [ ] All pages load in < 3 seconds
- [ ] Map renders smoothly with 298K points (WebGL)
- [ ] What-if simulation completes in < 5 seconds
- [ ] 24-hour animation plays smoothly
- [ ] Mobile responsive (basic — not primary target)

---

## 5.5 Phase 5 Deliverables

| Deliverable | Description |
|---|---|
| FastAPI backend | All endpoints functional |
| Next.js dashboard | 7 pages, all interactive |
| Export pipeline | All data exported for frontend |
| Docker setup | Backend + frontend containerized |
| Cloud deployment | Publicly accessible demo URL |
| Demo recording | Screen recording of full walkthrough |

### Exit Criteria:
- [ ] All 7 pages render correctly
- [ ] All API endpoints return valid data
- [ ] Impact map renders 298K violations smoothly
- [ ] What-if simulator works interactively
- [ ] 24-hour risk animation plays
- [ ] Propagation animation works
- [ ] Dark mode design is visually polished
- [ ] Deployed to cloud and accessible
- [ ] 2-minute demo script prepared
