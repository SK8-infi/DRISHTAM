# DRISHTAM — Novel Enhancement Layers

> These four layers are woven into the existing 5-phase plan.  
> They transform DRISHTAM from a traffic tool into a **policy + sustainability platform**.

---

## LAYER A: Economic Cost Quantification (💰)

**Where it fits**: Phase 2 (after PIS computation) + Phase 5 (dashboard KPIs)

**Core idea**: Convert every PIS score to **₹ lost per hour**.

### Methodology:
- Bengaluru annual congestion cost: **₹1.47 lakh crore** (~$22B) across ~5M commuters
- Per-vehicle-hour cost: ₹1,47,00,000 lakh / (5M vehicles × 250 working days × 2 peak hours) ≈ **₹58.8/vehicle-hour**
- A violation with PIS=80 on a road carrying ~500 vehicles/hour during peak:
  - Effective delay factor = PIS/100 × 0.3 (30% capacity → proportional delay)
  - Cost = 500 vehicles × ₹58.8 × 0.24 delay = **₹7,056/hour**

### Output:
- `cost_per_hour_inr` column per violation
- City-wide daily/monthly/annual cost estimate
- Per-scenario cost savings in What-If engine ("Enforce top 50 roads → save ₹X crore/year")
- Dashboard: ₹ ticker showing estimated daily cost

### Research reference: Economic Survey 2025-26 congestion cost data, TomTom Traffic Index

---

## LAYER B: Carbon Impact Score (🌍)

**Where it fits**: Phase 2 (after PIS) + Phase 5 (dashboard)

**Core idea**: Each violation has a CO₂ footprint from induced idle time.

### Methodology:
- Average idle fuel consumption: **0.8 L/hour** (petrol car), **1.2 L/hour** (diesel)
- CO₂ per liter: petrol = **2.31 kg**, diesel = **2.68 kg**
- Per vehicle idle emission: ~1.85 kg CO₂/hour (blended average)
- A PIS=80 violation on a 500-vehicle/hour road with 15% effective delay:
  - Induced idle time = 500 × 0.15 × (average delay in hours)
  - CO₂ = induced_idle_hours × 1.85 kg
- Aggregate: "41K high-impact violations → X,000 tonnes CO₂/year"

### Output:
- `co2_kg_per_hour` column per violation
- Annual citywide CO₂ from parking-induced congestion
- "Trees equivalent" metric (1 tree absorbs ~22 kg CO₂/year)
- Scenario: "Enforce top 50 roads → save X tonnes CO₂ = planting Y trees"
- Dashboard: Carbon cost card with tree equivalent

### Research reference: IPCC emission factors, MoRTH India fuel consumption data

---

## LAYER C: Enforcement Equity Analysis (⚖️)

**Where it fits**: Phase 2 (new EDA section) + Phase 5 (dedicated dashboard section)

**Core idea**: Is enforcement proportional to impact, or biased by geography?

### Methodology:
1. **Detection equity**: violations_detected / estimated_actual_violations per zone
   - High-camera zones have more detections → doesn't mean more violations
2. **Enforcement intensity**: violations/km² per police station
3. **Impact equity**: Compare enforcement_intensity vs PIS_density per zone
   - "Zone A: 50 violations/km², mean PIS=25 → 12.5 PIS-units/km²"
   - "Zone B: 10 violations/km², mean PIS=65 → 6.5 PIS-units/km²"
   - Zone A gets 5× more enforcement despite Zone B having higher per-violation impact
4. **Temporal equity**: Morning enforcement = 80%, evening = 5% (from EDA #1)
   - But evening PIS is HIGHER (rush hour temporal factor)
5. **Vehicle equity**: Are two-wheelers (46%) over-represented in enforcement despite low PIS?

### Output:
- Equity index per police station (enforcement_intensity / PIS_density)
- "Over-enforced" and "under-enforced" zone maps
- Temporal equity chart (enforcement vs. impact by hour)
- Vehicle type enforcement bias chart
- Policy recommendations: "Redistribute X officers from Zone A to Zone B for 15% more impact reduction"

---

## LAYER D: Multi-Modal Impact (🚌)

**Where it fits**: Phase 1 (data enrichment) + Phase 2 (PIS modifier)

**Core idea**: Violations near transit stops affect THOUSANDS of passengers, not just cars.

### Methodology:
1. **Bus stop proximity**: From OSM, extract BMTC bus stop locations
   - Violations within 50m of bus stop → `is_near_bus_stop = True`
   - Weight by estimated daily bus ridership at that stop
2. **Metro station proximity**: Namma Metro stations from OSM/MapMyIndia
   - Violations within 200m of metro → `is_near_metro = True`
   - Metro stations have ~15,000-50,000 daily passengers
3. **Passenger-weighted PIS modifier**:
   ```
   modal_multiplier = 1.0  # default
   if near_bus_stop: modal_multiplier += 0.3 × (estimated_daily_passengers / 1000)
   if near_metro: modal_multiplier += 0.5 × (daily_ridership / 10000)
   
   PIS_multimodal = PIS × min(modal_multiplier, 2.5)
   ```
4. **BMTC breakdown correlation**: 30% of traffic events are BMTC breakdowns
   - Violations that block bus lanes compound BMTC delays

### Output:
- `pis_multimodal` column (PIS adjusted for transit proximity)
- "Passenger-hours lost" metric per violation
- Map overlay: violations near transit colored differently
- "This violation near Majestic metro delays ~30,000 passengers/day"

---

## Future Ideas Backlog

For potential Phase 6+ or v2.0:

| # | Idea | Complexity | Impact |
|---|---|---|---|
| 1 | **Network Vulnerability Index** — identify "kill switch" road segments | Medium | High |
| 2 | **RL Patrol Optimization** — optimize officer routes for max PIS reduction | High | Very High |
| 3 | **Time-Series Anomaly Detection** — flag unusual violation spikes | Medium | Medium |
| 4 | **Transferability Framework** — make DRISHTAM city-agnostic | Medium | Very High |
| 5 | **Real-time Streaming** — process violations as they arrive | High | High |
| 6 | **Accessibility Impact** — violations blocking wheelchair ramps | Low | Medium |
| 7 | **Event Surge Modeling** — predict parking chaos during festivals | Medium | High |
| 8 | **Digital Twin Integration** — connect with BTP's planned MDT | High | Very High |
