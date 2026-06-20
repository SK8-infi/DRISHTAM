"use client";

import { useState, useCallback, useEffect, Suspense } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchWhatIfRoads, runWhatIf, fetchSegments, fetchStations, runStationOptimize, type WhatIfResult } from "@/lib/api";
import ReductionGauge from "@/components/ReductionGauge";
import dynamic from "next/dynamic";

const PropagationMap = dynamic(() => import("@/components/Map/PropagationMap"), { ssr: false });

/* ── SVG Icons ──────────────────────────────────────────── */
const SvgIcons = {
  crosshair: (color: string) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>,
  sunset: (color: string) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 18a5 5 0 0 0-10 0"/><line x1="12" y1="9" x2="12" y2="2"/><line x1="4.22" y1="10.22" x2="5.64" y2="11.64"/><line x1="1" y1="18" x2="3" y2="18"/><line x1="21" y1="18" x2="23" y2="18"/><line x1="18.36" y1="11.64" x2="19.78" y2="10.22"/><line x1="23" y1="22" x2="1" y2="22"/><polyline points="8 6 12 2 16 6"/></svg>,
  road: (color: string) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 2l2 18"/><path d="M19 2l-2 18"/><path d="M12 6v2"/><path d="M12 12v2"/><path d="M12 18v2"/></svg>,
  building: (color: string) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><path d="M9 22V12h6v10"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/></svg>,
  simulator: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v18"/><path d="m8 8 4-5 4 5"/><path d="M4 14a4 4 0 0 0 4 4"/><path d="M20 14a4 4 0 0 1-4 4"/><circle cx="12" cy="12" r="1"/></svg>,
  play: <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  chart: <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.3"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  loader: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></svg>,
};

/* ── Scenario Cards ─────────────────────────────────────── */
const SCENARIOS = [
  {
    id: "top5",
    iconFn: SvgIcons.crosshair,
    title: "Top 5 Roads",
    subtitle: "Enforce worst offenders",
    roads: ["Service Road", "Outer Ring Road", "Subedar Chatram Road", "Whitefield Road", "Swamy Vivekananda Road"],
    accent: "#3b82f6",
  },
  {
    id: "evening",
    iconFn: SvgIcons.sunset,
    title: "Evening Peak",
    subtitle: "4-8 PM coverage",
    roads: ["Hosur Road", "Mysore Road", "Tumkur Road", "Bellary Road"],
    accent: "#f59e0b",
  },
  {
    id: "orr",
    iconFn: SvgIcons.road,
    title: "ORR Corridor",
    subtitle: "Full Outer Ring Road",
    roads: ["Outer Ring Road"],
    accent: "#8b5cf6",
  },
  {
    id: "cbd",
    iconFn: SvgIcons.building,
    title: "CBD Core",
    subtitle: "MG Road + Brigade",
    roads: ["Mahatma Gandhi Road", "St. John's Road", "Palace Road", "Dispensary Road"],
    accent: "#06b6d4",
  },
];

import { useSearchParams } from "next/navigation";

function WhatIfContent() {
  const searchParams = useSearchParams();
  const initRoads = searchParams.get("roads")?.split(",").filter(Boolean) || [];
  const initStation = searchParams.get("station") || "";

  const [search, setSearch] = useState("");
  const [selectedRoads, setSelectedRoads] = useState<string[]>(initRoads);
  const [selectedStation, setSelectedStation] = useState<string>(initStation);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [stationResult, setStationResult] = useState<any>(null);
  const [activeScenario, setActiveScenario] = useState<string | null>(initRoads.length > 0 ? "custom" : null);

  const { data: stationsData } = useQuery({
    queryKey: ["stations"],
    queryFn: () => fetchStations(),
  });

  const { data: roads } = useQuery({
    queryKey: ["whatif-roads", search],
    queryFn: () => fetchWhatIfRoads(search),
    enabled: search.length >= 0,
  });

  const mutation = useMutation({
    mutationFn: (args: { roadNames: string[]; segIndices?: number[] }) =>
      runWhatIf(args.roadNames, args.segIndices),
    onSuccess: (data) => { setResult(data); setStationResult(null); },
  });

  const stationMutation = useMutation({
    mutationFn: (stationName: string) => runStationOptimize({ station: stationName, n_officers: 50 }),
    onSuccess: (data) => { setStationResult(data); setResult(null); },
  });

  // Auto-run if URL params were provided
  useEffect(() => {
    if (initRoads.length > 0 && !result && !mutation.isPending) {
      mutation.mutate({ roadNames: initRoads });
    }
    if (initStation && !stationResult && !stationMutation.isPending) {
      setSelectedStation(initStation);
      stationMutation.mutate(initStation);
    }
  }, [initRoads, initStation, result, stationResult, mutation, stationMutation]);

  const toggleRoad = (road: string) => {
    setActiveScenario(null);
    setSelectedStation("");
    setSelectedRoads((prev) =>
      prev.includes(road) ? prev.filter((r) => r !== road) : [...prev, road]
    );
  };

  const runScenario = useCallback((scenario: typeof SCENARIOS[0]) => {
    setActiveScenario(scenario.id);
    setSelectedStation("");
    setSelectedRoads(scenario.roads);
    mutation.mutate({ roadNames: scenario.roads });
  }, [mutation]);

  const runCustom = useCallback(() => {
    if (selectedStation) {
      stationMutation.mutate(selectedStation);
      return;
    }
    if (selectedRoads.length === 0) return;
    mutation.mutate({ roadNames: selectedRoads });
  }, [selectedRoads, selectedStation, mutation, stationMutation]);

  // Point-in-polygon test (ray casting)
  const pointInPolygon = useCallback((lat: number, lon: number, polygon: [number, number][]) => {
    if (polygon.length < 3) return true; // fallback to bbox-only
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i][0], yi = polygon[i][1];
      const xj = polygon[j][0], yj = polygon[j][1];
      const intersect = ((yi > lon) !== (yj > lon)) && (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }, []);

  // Handle area drawn on map
  const handleAreaSelected = useCallback(async (
    bbox: { lat_min: number; lat_max: number; lon_min: number; lon_max: number },
    polygon: [number, number][]
  ) => {
    try {
      const data = await fetchSegments({ ...bbox, min_impact: 0, limit: 5000 });
      
      const insideSegments = polygon.length >= 3
        ? data.segments.filter(seg => pointInPolygon(seg.lat, seg.lon, polygon))
        : data.segments;

      if (insideSegments.length === 0) return;

      const uniqueRoads = [...new Set(
        insideSegments
          .map(s => s.road_name)
          .filter(name => name && name !== "Unnamed" && name !== "")
      )];

      const segIndices = insideSegments.map(s => s.seg_idx);

      setActiveScenario("draw");
      setSelectedRoads(uniqueRoads);
      mutation.mutate({ roadNames: uniqueRoads, segIndices });
    } catch (e) {
      console.error("Area selection failed:", e);
    }
  }, [mutation, pointInPolygon]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)", overflow: "hidden" }}>
      {/* Header */}
      <div style={{
        padding: "16px 24px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ color: "var(--accent)" }}>{SvgIcons.simulator}</span> What-If Simulator
          </h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
            Enforce roads and watch the impact propagate through the network in real-time
          </p>
        </div>
        {mutation.isPending && (
          <div style={{
            display: "flex", alignItems: "center", gap: "8px",
            padding: "6px 16px", borderRadius: "20px",
            background: "rgba(59, 130, 246, 0.15)", border: "1px solid rgba(59, 130, 246, 0.3)",
            fontSize: "12px", fontWeight: 600, color: "#60a5fa",
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: "#3b82f6",
              animation: "pulse 1.5s ease-in-out infinite",
            }} />
            Computing simulation...
          </div>
        )}
      </div>

      {/* Main 3-Panel Layout */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* ── LEFT PANEL: Road Selector ──────────────────── */}
        <div style={{
          width: "320px", flexShrink: 0,
          borderRight: "1px solid var(--border)",
          display: "flex", flexDirection: "column",
          overflow: "hidden",
        }}>
          {/* Scenario Cards */}
          <div style={{ padding: "16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "10px" }}>
              QUICK SCENARIOS
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => runScenario(s)}
                  style={{
                    padding: "10px",
                    background: activeScenario === s.id ? `${s.accent}15` : "var(--bg-elevated)",
                    border: `1px solid ${activeScenario === s.id ? `${s.accent}50` : "var(--border)"}`,
                    borderRadius: "8px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.2s ease",
                    color: activeScenario === s.id ? s.accent : "var(--text-secondary)",
                  }}
                >
                  <div style={{ marginBottom: "4px" }}>{s.iconFn(activeScenario === s.id ? s.accent : "var(--text-muted)")}</div>
                  <div style={{ fontSize: "12px", fontWeight: 700 }}>{s.title}</div>
                  <div style={{ fontSize: "10px", opacity: 0.7 }}>{s.subtitle}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Station/Division Constraint */}
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "8px" }}>
              CONSTRAIN TO STATION
            </div>
            <select
              value={selectedStation}
              onChange={(e) => {
                setSelectedStation(e.target.value);
                setActiveScenario(null);
                setSelectedRoads([]);
              }}
              style={{
                width: "100%", padding: "8px 12px", background: "var(--bg-elevated)",
                border: "1px solid var(--border)", borderRadius: "6px",
                color: "var(--text-primary)", fontSize: 12, outline: "none",
                fontFamily: "var(--font-sans)",
              }}
            >
              <option value="">Global (All Stations)</option>
              {stationsData?.map((stn: any) => (
                <option key={stn.station_name} value={stn.station_name}>
                  {stn.station_name} ({stn.division})
                </option>
              ))}
            </select>
          </div>

          {/* Search & Road List */}
          <div style={{ padding: "12px 16px", flexShrink: 0, opacity: selectedStation ? 0.5 : 1, pointerEvents: selectedStation ? "none" : "auto" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "8px" }}>
              CUSTOM ROAD SELECTION
            </div>
            <input
              type="text"
              placeholder="Search roads..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: "100%", padding: "8px 12px", background: "var(--bg-elevated)",
                border: "1px solid var(--border)", borderRadius: "6px",
                color: "var(--text-primary)", fontSize: 12, outline: "none",
                fontFamily: "var(--font-sans)",
              }}
            />
          </div>

          {/* Selected chips */}
          {selectedRoads.length > 0 && (
            <div style={{ padding: "0 16px 8px", display: "flex", flexWrap: "wrap", gap: 4, flexShrink: 0 }}>
              {selectedRoads.map((road) => (
                <span
                  key={road}
                  onClick={() => toggleRoad(road)}
                  style={{
                    padding: "3px 8px", borderRadius: 100, fontSize: 10, fontWeight: 600,
                    background: "rgba(59, 130, 246, 0.15)", color: "#60a5fa", cursor: "pointer",
                    border: "1px solid rgba(59, 130, 246, 0.3)",
                  }}
                >
                  {road} ✕
                </span>
              ))}
            </div>
          )}

          {/* Road list */}
          <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid var(--border)" }}>
            {(roads?.roads || []).map((road) => (
              <div
                key={road}
                onClick={() => toggleRoad(road)}
                style={{
                  padding: "8px 16px", cursor: "pointer", fontSize: 12,
                  borderBottom: "1px solid var(--border)",
                  background: selectedRoads.includes(road) ? "rgba(59, 130, 246, 0.08)" : "transparent",
                  color: selectedRoads.includes(road) ? "#60a5fa" : "var(--text-secondary)",
                  transition: "all 0.15s ease",
                  display: "flex", alignItems: "center", gap: "8px",
                }}
              >
                <div style={{
                  width: 14, height: 14, borderRadius: 3,
                  border: `1.5px solid ${selectedRoads.includes(road) ? "#3b82f6" : "var(--border)"}`,
                  background: selectedRoads.includes(road) ? "#3b82f6" : "transparent",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "9px", color: "#fff",
                }}>
                  {selectedRoads.includes(road) && "✓"}
                </div>
                {road}
              </div>
            ))}
          </div>

          {/* Run Button */}
          <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
            <button
              onClick={runCustom}
              disabled={(!selectedStation && selectedRoads.length === 0) || mutation.isPending || stationMutation.isPending}
              style={{
                width: "100%", padding: "10px", borderRadius: "8px",
                background: (selectedStation || selectedRoads.length > 0) ? "linear-gradient(135deg, #3b82f6, #8b5cf6)" : "var(--bg-elevated)",
                border: "none", cursor: (selectedStation || selectedRoads.length > 0) ? "pointer" : "not-allowed",
                color: "#fff", fontSize: "13px", fontWeight: 700,
                opacity: (mutation.isPending || stationMutation.isPending) ? 0.6 : 1,
                transition: "all 0.2s ease",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
                {(mutation.isPending || stationMutation.isPending) ? <>{SvgIcons.loader} Computing...</> : <>{SvgIcons.play} Run Simulation</>}
              </span>
            </button>
          </div>
        </div>

        {/* ── CENTER: Propagation Map ───────────────────── */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <PropagationMap 
            result={stationResult ? {
              road_names: [...new Set(stationResult.assignments.map((a: any) => a.road_name))],
              segments_affected: stationResult.total_assignments,
              violations_removed: 0,
              baseline_impact: 0,
              new_impact: 0,
              impact_reduction: 0,
              pct_reduction: 0,
              segments_improved: 0,
              top_improved: [],
              propagation: []
            } as unknown as WhatIfResult : result} 
            onAreaSelected={handleAreaSelected} 
          />
        </div>

        {/* ── RIGHT PANEL: Results ──────────────────────── */}
        <div style={{
          width: "320px", flexShrink: 0,
          borderLeft: "1px solid var(--border)",
          display: "flex", flexDirection: "column",
          overflow: "hidden",
        }}>
          {!result && !stationResult ? (
            <div style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
              padding: "40px", textAlign: "center",
            }}>
              <div>
                <div style={{ marginBottom: "12px", color: "var(--text-muted)" }}>{SvgIcons.chart}</div>
                <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                  Results will appear here<br/>after running a simulation
                </div>
              </div>
            </div>
          ) : stationResult ? (
            <div style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
              <h3 style={{ marginTop: 0, marginBottom: "20px", fontSize: "16px", color: "var(--text-primary)" }}>Patrol Optimization</h3>
              
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "24px" }}>
                <div className="card" style={{ padding: "16px", background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Assignments</div>
                  <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--accent)" }}>{stationResult.total_assignments}</div>
                </div>
                <div className="card" style={{ padding: "16px", background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Expected ROI</div>
                  <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--success)" }}>{stationResult.total_roi}</div>
                </div>
              </div>

              <h4 style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "12px", textTransform: "uppercase" }}>Allocated Roads</h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {stationResult.assignments.map((a: any, i: number) => (
                  <div key={i} style={{ padding: "12px", background: "rgba(255,255,255,0.05)", borderRadius: "8px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>{a.road_name}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-muted)" }}>
                      <span>Officer ID: {a.officer_id}</span>
                      <span style={{ color: "var(--success)" }}>ROI: {a.expected_roi}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : result && (
            <div style={{ flex: 1, overflowY: "auto" }}>
              {/* Animated Gauge */}
              <div style={{
                padding: "24px", borderBottom: "1px solid var(--border)",
                display: "flex", justifyContent: "center",
                position: "relative",
                minHeight: "220px",
              }}>
                <ReductionGauge percentage={result.pct_reduction} />
              </div>

              {/* KPI Row */}
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr",
                gap: "1px", background: "var(--border)",
                borderBottom: "1px solid var(--border)",
              }}>
                <div style={{ padding: "12px 16px", background: "var(--bg-primary)" }}>
                  <div style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-muted)", letterSpacing: "0.3px" }}>SEGMENTS</div>
                  <div style={{ fontSize: "22px", fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    {result.segments_affected}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>{result.segments_improved} improved</div>
                </div>
                <div style={{ padding: "12px 16px", background: "var(--bg-primary)" }}>
                  <div style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-muted)", letterSpacing: "0.3px" }}>VIOLATIONS</div>
                  <div style={{ fontSize: "22px", fontWeight: 800, fontFamily: "var(--font-mono)", color: "#ef4444" }}>
                    {result.violations_removed}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>removed daily</div>
                </div>
              </div>

              {/* Cost-Benefit */}
              {result.cost_benefit && (
                <div style={{
                  padding: "16px", borderBottom: "1px solid var(--border)",
                }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "12px" }}>
                    COST-BENEFIT ANALYSIS
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Officers Needed</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)" }}>
                        {result.cost_benefit.officers_needed}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Daily Cost</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "#ef4444" }}>
                        ₹{result.cost_benefit.cost_per_day_lakhs.toFixed(2)}L
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Congestion Saved</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "#22c55e" }}>
                        ₹{result.cost_benefit.congestion_saved_crore.toFixed(3)}Cr
                      </span>
                    </div>
                    <div style={{
                      display: "flex", justifyContent: "space-between", fontSize: "12px",
                      padding: "8px 0", borderTop: "1px solid var(--border)", marginTop: "4px",
                    }}>
                      <span style={{ color: "var(--text-primary)", fontWeight: 700 }}>ROI Multiplier</span>
                      <span style={{
                        fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: "16px",
                        color: "#22c55e",
                        textShadow: "0 0 12px rgba(34, 197, 94, 0.4)",
                      }}>
                        {result.cost_benefit.roi_multiplier.toFixed(1)}×
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Propagation Rings */}
              {result.propagation.length > 0 && (
                <div style={{ padding: "16px", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "12px" }}>
                    NETWORK PROPAGATION
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {result.propagation.map((ring) => {
                      const hopColors: Record<number, string> = { 0: "#22c55e", 1: "#eab308", 2: "#f97316" };
                      const hopLabels: Record<number, string> = { 0: "Direct", 1: "1-Hop", 2: "Ripple" };
                      const color = hopColors[ring.hop] || "#6b7280";
                      return (
                        <div key={ring.hop} style={{
                          display: "flex", alignItems: "center", gap: "12px",
                          padding: "10px 12px",
                          background: `${color}08`,
                          border: `1px solid ${color}30`,
                          borderRadius: "8px",
                        }}>
                          <div style={{
                            width: 36, height: 36, borderRadius: "50%",
                            border: `2px solid ${color}`,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: "14px", fontWeight: 800, fontFamily: "var(--font-mono)",
                            color,
                          }}>
                            {ring.hop}
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: "12px", fontWeight: 700, color }}>
                              {hopLabels[ring.hop] || `Hop ${ring.hop}`}
                            </div>
                            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                              {ring.segments} segments · Δ {ring.total_improvement.toFixed(1)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Top Improved */}
              {result.top_improved.length > 0 && (
                <div style={{ padding: "16px" }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "12px" }}>
                    TOP IMPROVED SEGMENTS
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    {result.top_improved.slice(0, 8).map((seg, i) => (
                      <div key={i} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 8px", borderRadius: "6px",
                        background: i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent",
                        fontSize: "11px",
                      }}>
                        <span style={{ color: "var(--text-secondary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {seg.road_name}
                        </span>
                        <span style={{ fontFamily: "var(--font-mono)", color: "#22c55e", fontWeight: 600, marginLeft: "8px" }}>
                          -{seg.improvement.toFixed(3)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function WhatIfPage() {
  return (
    <Suspense fallback={
      <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
        Loading simulator...
      </div>
    }>
      <WhatIfContent />
    </Suspense>
  );
}
