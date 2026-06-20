# Phase 3B — Digital Twin Traffic Simulation

> **DRISHTAM Research Document 09**
> Generated: 2026-06-19, 03:35 IST
> Simulation: v6 (360 zones, ×1.2 demand, FW max 50 iterations)

## 1. Summary

We built a macroscopic traffic digital twin for Bangalore city to quantify the
traffic impact of parking violations. The twin uses Frank-Wolfe user equilibrium
assignment on a 155K-node / 394K-edge road network derived from OpenStreetMap,
with gravity-model origin-destination demand calibrated to census population
(360 traffic analysis zones, ×1.2 demand multiplier).

**Key finding**: Parking violations cause **up to +30.9% increase in
Vehicle-Hours-Travelled (VHT)** during peak hours, reducing city-wide average
speeds from 8.3 km/h to 6.5 km/h at the PM peak.

---

## 2. Configuration

| Parameter | Value |
|-----------|-------|
| Road network | 155,359 nodes, 393,717 edges (OSM Bangalore) |
| Traffic zones | 360 (population-weighted, dynamic sizing) |
| Demand multiplier | ×1.2 (calibrated to realistic V/C) |
| FW max iterations | 50 (convergence threshold: gap < 0.01) |
| BPR parameters | α=0.15, β=4.0 (IRC standard) |
| Time periods | 6 hours (03:00, 06:00, 09:00, 12:00, 17:00, 21:00) |
| Violations mapped | 223,304 violations → 94,667 edges (mean capacity blocked = 18.4%) |
| Compute | e2-standard-8 (8 vCPU, 32 GB RAM), ~8 hours total |

### Demand Profile (PCU/hr)

| Hour | Demand | Description |
|------|--------|-------------|
| 03:00 | 21,118 | Night minimum |
| 06:00 | 118,286 | Early morning |
| 09:00 | 459,184 | AM peak |
| 12:00 | 667,446 | Midday |
| 17:00 | 685,767 | PM peak (highest) |
| 21:00 | 263,330 | Evening off-peak |

---

## 3. Baseline Scenario Results

Traffic assignment under normal road capacity (no parking obstructions).

| Hour | PCU/hr | Mean V/C | Max V/C | VKT (km) | VHT (hrs) | Eff. Speed (km/h) | FW iters | Runtime |
|------|--------|----------|---------|-----------|-----------|-------------------|----------|---------|
| 03:00 | 21,118 | 0.01 | 0.77 | 329,516 | 9,128 | 36.1 | 3 | 4.5 min |
| 06:00 | 118,286 | 0.07 | 3.73 | 2,755,834 | 85,954 | 32.1 | 5 | 7.1 min |
| 09:00 | 459,184 | 0.34 | 11.87 | 10,968,146 | 998,645 | 11.0 | 47 | 67.2 min |
| 12:00 | 667,446 | 0.43 | 7.33 | 13,189,437 | 1,222,307 | 10.8 | 48 | 67.0 min |
| 17:00 | 685,767 | 0.51 | 10.84 | 15,159,693 | 1,820,716 | 8.3 | 50 | 67.9 min |
| 21:00 | 263,330 | 0.13 | 3.97 | 5,090,783 | 183,362 | 27.8 | ~30 | 25.2 min |

### Validation

| Metric | Our Model | Real Bangalore | Source |
|--------|-----------|---------------|--------|
| PM peak eff. speed | **8.3 km/h** | 8–12 km/h | TomTom Traffic Index 2024 |
| AM peak eff. speed | **11.0 km/h** | 10–14 km/h | Google Maps typical travel times |
| Night speed | **36.1 km/h** | 30–40 km/h | DULT speed surveys |
| PM > AM asymmetry | **Yes** (0.51 vs 0.34) | Yes | Known Bangalore pattern |

The effective speed metric provides strong validation — our PM peak speed of
8.3 km/h closely matches real-world data from TomTom and Google Maps.

---

## 4. Violation Scenario Results

Traffic assignment with parking-violation-reduced capacity on 94,667 affected
edges (capacity reduced by mean 18.4%).

| Hour | PCU/hr | Mean V/C | Max V/C | VKT (km) | VHT (hrs) | Eff. Speed (km/h) | FW iters | Runtime |
|------|--------|----------|---------|-----------|-----------|-------------------|----------|---------|
| 03:00 | 21,118 | 0.01 | 0.77 | 325,527 | 8,993 | 36.2 | 3 | 4.6 min |
| 06:00 | 118,286 | 0.07 | 5.68 | 2,707,236 | 87,120 | 31.1 | 5 | 9.2 min |
| 09:00 | 459,184 | 0.38 | 11.87 | 10,907,592 | 1,126,257 | 9.7 | 50 | 64.7 min |
| 12:00 | 667,446 | 0.49 | 8.27 | 13,427,395 | 1,600,517 | 8.4 | 50 | 68.4 min |
| 17:00 | 685,767 | 0.57 | 10.84 | 15,354,445 | 2,364,248 | 6.5 | 50 | 71.7 min |
| 21:00 | 263,330 | 0.14 | 4.17 | 5,042,198 | 189,958 | 26.5 | ~30 | 32.5 min |

---

## 5. Impact Analysis — Baseline vs Violation

### Vehicle-Hours-Travelled (VHT) Delta

| Hour | Baseline VHT | Violation VHT | Δ VHT | **% Change** |
|------|-------------|---------------|-------|-------------|
| 03:00 | 9,128 | 8,993 | -135 | -1.5% |
| 06:00 | 85,954 | 87,120 | +1,166 | **+1.4%** |
| 09:00 | 998,645 | 1,126,257 | +127,612 | **+12.8%** |
| 12:00 | 1,222,307 | 1,600,517 | +378,210 | **+30.9%** |
| **17:00** | **1,820,716** | **2,364,248** | **+543,532** | **+29.9%** |
| 21:00 | 183,362 | 189,958 | +6,596 | **+3.6%** |
| **Daily Total** | **4,320,112** | **5,377,093** | **+1,056,981** | **+24.5%** |

### Congestion (Mean V/C) Delta

| Hour | Baseline | Violation | **% Change** |
|------|----------|-----------|-------------|
| 03:00 | 0.01 | 0.01 | 0% |
| 06:00 | 0.07 | 0.07 | 0% |
| 09:00 | 0.34 | 0.38 | **+11.8%** |
| 12:00 | 0.43 | 0.49 | **+14.0%** |
| **17:00** | **0.51** | **0.57** | **+11.8%** |
| 21:00 | 0.13 | 0.14 | **+7.7%** |

### Effective Speed Impact

| Hour | Baseline (km/h) | Violation (km/h) | **Speed Drop** |
|------|-----------------|------------------|---------------|
| 03:00 | 36.1 | 36.2 | 0% |
| 06:00 | 32.1 | 31.1 | -3.1% |
| 09:00 | 11.0 | 9.7 | **-11.8%** |
| 12:00 | 10.8 | 8.4 | **-22.2%** |
| **17:00** | **8.3** | **6.5** | **-21.7%** |
| 21:00 | 27.8 | 26.5 | -4.7% |

---

## 6. Key Findings

### 6.1 Non-linear Amplification
Parking violations have a **non-linear** impact — the same 18.4% mean capacity
reduction causes:
- **0% effect** at night (V/C ≪ 1, spare capacity absorbs it)
- **+12% VHT** at moderate demand (AM peak)
- **+30% VHT** at high demand (midday/PM peak)

This is the classic "last straw" effect in traffic engineering — when roads are
already near capacity, even small capacity reductions cause disproportionate delays.

### 6.2 PM Peak is Most Affected
The PM peak (17:00) sees the largest absolute impact:
- **+543,532 extra vehicle-hours** of delay city-wide
- Average speed drops from **8.3 to 6.5 km/h** (-22%)
- Every commuter's PM journey takes **~22% longer** due to parking violations

### 6.3 Speed Validation
Our baseline PM peak speed of 8.3 km/h matches real-world Bangalore data
(TomTom: 8–12 km/h), providing strong evidence that the digital twin produces
realistic traffic patterns.

### 6.4 Daily Aggregate
Across all 6 simulated hours, parking violations add **+1,056,981 vehicle-hours**
of delay — a **+24.5% increase** in total travel time city-wide.

---

## 7. Delay Metrics for GNN

The simulation produces per-edge delay metrics (`delay_metrics.parquet`):
- **393,717 edges** analyzed
- **174,729 segments** (44.4%) show positive delay impact
- Target variable: `impact_score` = δ_flow × δ_time per edge
- Used as physics-based supervision for GNN re-training (Phase 3C)

---

## 8. Limitations & Future Work

1. **Max V/C values** (up to 11.87) indicate demand concentration on a few
   corridors — future work should refine zone connectors for more even distribution
2. **Static demand** — current model uses fixed hourly demand; dynamic
   departure-time choice would improve realism
3. **No route choice elasticity** — travelers always take shortest path; real
   behavior includes mode switching and trip cancellation at high congestion
4. **Gravity model calibration** — the impedance function could be calibrated
   against observed trip length distributions from BMTC data
5. **Violation temporal patterns** — currently uses daily average; time-of-day
   variation in parking violations would improve accuracy

---

## 9. References

1. Bureau of Public Roads (BPR) Volume-Delay Function, 1964
2. Frank, M. and Wolfe, P. "An Algorithm for Quadratic Programming", 1956
3. IRC:106-1990 "Guidelines for Capacity of Urban Roads in Plain Areas"
4. TomTom Traffic Index — Bangalore 2024
5. DULT Bangalore Comprehensive Mobility Plan, 2019
