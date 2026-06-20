# DRISHTAM Dashboard

Interactive Next.js 15 frontend for the DRISHTAM predictive enforcement intelligence system.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | **Overview** | Animated KPIs, Pareto donut, hourly sparklines, top roads table |
| `/map` | **Impact Map** | 393K road segments as polylines, 3 lens modes (Impact/Patrol/Risk), segment drill-down |
| `/whatif` | **What-If Simulator** | Scenario cards, propagation map, polygon area selection, reduction gauge |
| `/clusters` | **Cluster Explorer** | Bubble map of 1,087 HDBSCAN clusters, drill-down panel, What-If bridge |
| `/insights` | **Executive Insights** | 8 live findings, data quality scorecard, ML experiment log, pipeline diagram |

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **UI**: React 19 + vanilla CSS (OLED-dark theme)
- **Maps**: Leaflet + react-leaflet
- **Charts**: Recharts
- **Data Fetching**: TanStack React Query
- **Font**: Plus Jakarta Sans (Google Fonts)

## Getting Started

```bash
# Requires the FastAPI backend running on :8000
npm install
npm run dev    # → http://localhost:3001
```

## Architecture

```
src/
├── app/                    # Pages (5 routes)
│   ├── page.tsx            # Overview
│   ├── map/page.tsx        # Impact Map
│   ├── whatif/page.tsx     # What-If Simulator
│   ├── clusters/page.tsx   # Cluster Explorer
│   ├── insights/page.tsx   # Executive Insights
│   ├── layout.tsx          # Root layout
│   └── globals.css         # Design system
├── components/
│   ├── Layout/             # Sidebar, QueryProvider
│   ├── Map/                # SegmentMap, PropagationMap, ClusterBubbleMap, panels
│   └── Charts/             # ParetoDonut, HourlyChart, Sparkline, TopRoadsTable
└── lib/
    ├── api.ts              # Typed API client (14 endpoints)
    └── colors.ts           # Color utilities
```

## Design System

OLED-dark theme with CSS custom properties:
- Background: `#08080a` (pure black)
- Cards: `rgba(255, 255, 255, 0.03)` with `1px solid rgba(255, 255, 255, 0.06)`
- Accent: `#3b82f6` (blue-500)
- Font: Plus Jakarta Sans, monospace for numbers
- Animations: `animate-in` keyframe for staggered card reveals
