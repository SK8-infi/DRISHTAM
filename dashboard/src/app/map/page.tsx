"use client";

import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "@/lib/useDebounce";
import {
  fetchSegments,
  fetchSegmentDetail,
  fetchRiskAnimation,
  runStationOptimize,
  fetchStations,
  type SegmentLight,
  type SegmentDetail,
  type PatrolAssignment,
} from "@/lib/api";
import SegmentPanel from "@/components/Map/SegmentPanel";
import dynamic from "next/dynamic";

const SegmentMap = dynamic(() => import("@/components/Map/SegmentMap"), { ssr: false });

const DEFAULT_BBOX = { lat_min: 12.85, lat_max: 13.10, lon_min: 77.45, lon_max: 77.75 };
type MapMode = "impact" | "risk" | "patrol";

const Icons = {
  Map: <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/><line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/></svg>,
  Activity: <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  Target: <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>,
  Stations: <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>,
};

export default function MapPage() {
  const [mode, setMode] = useState<MapMode>("impact");
  const [bbox, setBbox] = useState(DEFAULT_BBOX);
  const [minImpact, setMinImpact] = useState(0.1);
  const [maxImpact, setMaxImpact] = useState(1.0);
  const [numOfficers, setNumOfficers] = useState(50);
  const [currentHour, setCurrentHour] = useState(9); // Default to morning peak
  const [selectedSeg, setSelectedSeg] = useState<SegmentDetail | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  // New states for Advanced Patrol Allocation
  const [allocationMode, setAllocationMode] = useState<"proportional" | "custom">("proportional");
  const [customAlloc, setCustomAlloc] = useState<Record<string, number>>({});

  // Debounce slider values to prevent API calls on every pixel
  const debouncedMinImpact = useDebounce(minImpact, 300);
  const debouncedMaxImpact = useDebounce(maxImpact, 300);
  const debouncedOfficers = useDebounce(numOfficers, 300);
  const debouncedHour = useDebounce(currentHour, 200);

  // 1. Impact Corridors
  const { data: segData, isLoading: isLoadingSegments } = useQuery({
    queryKey: ["segments", bbox, debouncedMinImpact, debouncedMaxImpact],
    queryFn: () => fetchSegments({ ...bbox, min_impact: debouncedMinImpact, max_impact: debouncedMaxImpact, limit: 5000 }),
    enabled: mode === "impact",
  });

  // 2. Risk Forecast
  const { data: riskData, isLoading: isLoadingRisk } = useQuery({
    queryKey: ["riskAnimation"],
    queryFn: () => fetchRiskAnimation(0, 23, 100),
    enabled: mode === "risk",
    staleTime: 5 * 60_000,
  });

  // 3. Optimal Patrol
  const { data: patrolData, isLoading: isLoadingPatrol } = useQuery({
    queryKey: ["optimize", debouncedOfficers, allocationMode, customAlloc],
    queryFn: async () => {
      if (allocationMode === "proportional") {
        return runStationOptimize({
          n_officers: debouncedOfficers,
          shifts: 3,
          hours_per_shift: 2,
        });
      } else {
        const totalReq = Object.values(customAlloc).reduce((a, b) => a + b, 0) || 0;
        if (totalReq === 0) {
          return { assignments: [] };
        }
        return runStationOptimize({
          n_officers: totalReq,
          shifts: 3,
          hours_per_shift: 2,
          custom_allocation: customAlloc
        });
      }
    },
    enabled: mode === "patrol",
    staleTime: 5 * 60_000,
  });

  // 4. Stations List for Custom Allocation
  const { data: stationsList } = useQuery({
    queryKey: ["allStationsList"],
    queryFn: () => fetchStations(),
    enabled: mode === "patrol" && allocationMode === "custom",
    staleTime: 5 * 60_000,
  });

  const handleSegmentClick = useCallback(async (seg: SegmentLight) => {
    try {
      const detail = await fetchSegmentDetail(seg.seg_idx);
      setSelectedSeg(detail);
      setPanelOpen(true);
    } catch (e) {
      console.error("Failed to fetch segment:", e);
    }
  }, []);

  const handleMapMove = useCallback((newBbox: typeof DEFAULT_BBOX) => {
    setBbox(newBbox);
  }, []);

  const getRiskSegments = () => {
    if (!riskData || !riskData.hourly_data) return [];
    return riskData.hourly_data[currentHour] || [];
  };

  const getPatrolAssignments = () => {
    const assignments = patrolData?.assignments || [];
    if (!assignments.length) return [];
    
    return assignments.filter((a) => 
      currentHour >= Number(a.hour_start) && 
      currentHour < Number(a.hour_end)
    );
  };

  const isModeLoading = 
    (mode === "impact" && isLoadingSegments) ||
    (mode === "risk" && isLoadingRisk) ||
    (mode === "patrol" && isLoadingPatrol);

  return (
    <div style={{ position: "relative", height: "calc(100vh - 56px)" }}>
      {/* Map Container (Background) */}
      <div style={{ position: "absolute", inset: 0, zIndex: 0 }}>
        <SegmentMap
          mode={mode}
          segments={(segData?.segments || []).filter((s) => s.impact_gbm >= minImpact && s.impact_gbm <= maxImpact)}
          riskSegments={getRiskSegments()}
          patrolAssignments={getPatrolAssignments() as unknown as PatrolAssignment[]}
          onSegmentClick={handleSegmentClick}
          onMapMove={handleMapMove}
        />
      </div>

      {/* Floating Lens Switcher (Top Left) */}
      <div id="map-lens-panel" role="radiogroup" aria-label="Map visualization mode" style={{
        position: "absolute",
        top: 24, left: 24,
        zIndex: 10,
        background: "rgba(10, 10, 10, 0.75)",
        backdropFilter: "blur(12px)",
        border: "1px solid var(--border)",
        borderRadius: "12px",
        padding: "8px",
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        width: "280px"
      }}>
        <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-light)", marginBottom: "4px" }}>
          <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600, color: "var(--text-primary)" }}>Map Lenses</h3>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)" }}>Select an analytical view</p>
        </div>

        <button 
          id="lens-impact"
          role="radio"
          aria-checked={mode === "impact"}
          aria-label="Impact Corridors: Road network bottleneck mapping"
          onClick={() => setMode("impact")}
          style={{
            display: "flex", alignItems: "center", gap: "12px",
            padding: "10px 12px",
            background: mode === "impact" ? "rgba(59, 130, 246, 0.15)" : "transparent",
            border: "1px solid",
            borderColor: mode === "impact" ? "rgba(59, 130, 246, 0.3)" : "transparent",
            borderRadius: "8px",
            color: mode === "impact" ? "#60a5fa" : "var(--text-secondary)",
            cursor: "pointer",
            textAlign: "left",
            transition: "all 0.2s ease"
          }}
        >
          <div style={{ color: mode === "impact" ? "#3b82f6" : "var(--text-muted)" }}>{Icons.Map}</div>
          <div>
            <div style={{ fontSize: "13px", fontWeight: 600 }}>Impact Corridors</div>
            <div style={{ fontSize: "11px", opacity: 0.7 }}>Road network bottleneck mapping</div>
          </div>
        </button>

        <button 
          id="lens-patrol"
          role="radio"
          aria-checked={mode === "patrol"}
          aria-label="Optimal Patrol: Simulated officer deployment"
          onClick={() => setMode("patrol")}
          style={{
            display: "flex", alignItems: "center", gap: "12px",
            padding: "10px 12px",
            background: mode === "patrol" ? "rgba(139, 92, 246, 0.15)" : "transparent",
            border: "1px solid",
            borderColor: mode === "patrol" ? "rgba(139, 92, 246, 0.3)" : "transparent",
            borderRadius: "8px",
            color: mode === "patrol" ? "#a78bfa" : "var(--text-secondary)",
            cursor: "pointer",
            textAlign: "left",
            transition: "all 0.2s ease"
          }}
        >
          <div style={{ color: mode === "patrol" ? "#8b5cf6" : "var(--text-muted)" }}>{Icons.Target}</div>
          <div>
            <div style={{ fontSize: "13px", fontWeight: 600 }}>Optimal Patrol</div>
            <div style={{ fontSize: "11px", opacity: 0.7 }}>Simulated officer deployment</div>
          </div>
        </button>

        <button 
          id="lens-risk"
          role="radio"
          aria-checked={mode === "risk"}
          aria-label="Risk Forecast: Hourly risk emergence heatmap"
          onClick={() => setMode("risk")}
          style={{
            display: "flex", alignItems: "center", gap: "12px",
            padding: "10px 12px",
            background: mode === "risk" ? "rgba(239, 68, 68, 0.15)" : "transparent",
            border: "1px solid",
            borderColor: mode === "risk" ? "rgba(239, 68, 68, 0.3)" : "transparent",
            borderRadius: "8px",
            color: mode === "risk" ? "#f87171" : "var(--text-secondary)",
            cursor: "pointer",
            textAlign: "left",
            transition: "all 0.2s ease"
          }}
        >
          <div style={{ color: mode === "risk" ? "#ef4444" : "var(--text-muted)" }}>{Icons.Activity}</div>
          <div>
            <div style={{ fontSize: "13px", fontWeight: 600 }}>Risk Forecast</div>
            <div style={{ fontSize: "11px", opacity: 0.7 }}>Hourly risk emergence heatmap</div>
          </div>
        </button>
      </div>

      {/* Bottom Floating Time Slider (for Risk/Patrol) */}
      {(mode === "risk" || mode === "patrol") && (
        <div style={{
          position: "absolute",
          bottom: 40, left: "50%", transform: "translateX(-50%)",
          zIndex: 10,
          background: "rgba(10, 10, 10, 0.85)",
          backdropFilter: "blur(12px)",
          border: "1px solid var(--border)",
          borderRadius: "32px",
          padding: "12px 32px",
          display: "flex",
          alignItems: "center",
          gap: "24px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          width: "600px"
        }}>
          <div style={{ color: "var(--text-muted)", fontSize: "12px", fontWeight: 600, minWidth: "40px" }}>
            {currentHour.toString().padStart(2, "0")}:00
          </div>
          <input
            type="range"
            min="0"
            max="23"
            step="1"
            value={currentHour}
            onChange={(e) => setCurrentHour(parseInt(e.target.value))}
            aria-label={`Time of day: ${currentHour.toString().padStart(2, "0")}:00`}
            aria-valuetext={`${currentHour.toString().padStart(2, "0")}:00`}
            style={{ flex: 1, accentColor: mode === "risk" ? "#ef4444" : "#8b5cf6" }}
          />
          <div style={{ color: "var(--text-muted)", fontSize: "12px", minWidth: "60px", textAlign: "right" }}>
            {mode === "risk" ? `${getRiskSegments().length} hotspots` : `${getPatrolAssignments().length} officers`}
          </div>
        </div>
      )}

      {/* Impact & Patrol Filters (Top Right) */}
      {(mode === "impact" || mode === "patrol") && (
        <div style={{
          position: "absolute",
          top: 24, right: 24,
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          alignItems: "flex-end"
        }}>
          {mode === "impact" && (
            <>
              {/* Min Impact Filter */}
              <div style={{
                background: "rgba(10, 10, 10, 0.75)",
                backdropFilter: "blur(12px)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                width: "240px"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>MIN IMPACT THRESHOLD</span>
                  <span style={{ fontSize: "12px", color: "var(--text-primary)", fontWeight: 600, background: "rgba(255,255,255,0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                    {minImpact.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={minImpact}
                  onChange={(e) => setMinImpact(parseFloat(e.target.value))}
                  aria-label={`Minimum impact threshold: ${minImpact.toFixed(2)}`}
                  aria-valuetext={minImpact.toFixed(2)}
                  style={{ width: "100%", accentColor: "#3b82f6" }}
                />
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "right" }}>
                  {isLoadingSegments ? "Computing network..." : `${segData?.count || 0} corridors active`}
                </div>
              </div>

              {/* Legend */}
              <div id="impact-severity-legend" style={{
                background: "rgba(10, 10, 10, 0.75)",
                backdropFilter: "blur(12px)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                padding: "16px",
                width: "240px"
              }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", marginBottom: 12 }}>
                  IMPACT SEVERITY
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {[
                    { color: "#16a34a", label: "Low (0-0.2)", min: 0.0, max: 0.2 },
                    { color: "#65a30d", label: "Medium (0.2-0.4)", min: 0.2, max: 0.4 },
                    { color: "#d97706", label: "High (0.4-0.6)", min: 0.4, max: 0.6 },
                    { color: "#ea580c", label: "Very High (0.6-0.8)", min: 0.6, max: 0.8 },
                    { color: "#dc2626", label: "Critical (0.8+)", min: 0.8, max: 1.0 },
                  ].map((item) => {
                    const isActive = minImpact === item.min && maxImpact === item.max;
                    return (
                      <button 
                        key={item.label} 
                        onClick={() => {
                          if (isActive) {
                            // Reset
                            setMinImpact(0.1);
                            setMaxImpact(1.0);
                          } else {
                            setMinImpact(item.min);
                            setMaxImpact(item.max);
                          }
                        }}
                        style={{ 
                          display: "flex", alignItems: "center", gap: "8px", 
                          fontSize: "12px", 
                          color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                          background: isActive ? "rgba(255,255,255,0.05)" : "transparent",
                          border: "none",
                          padding: "6px 8px",
                          borderRadius: "4px",
                          cursor: "pointer",
                          textAlign: "left",
                          fontWeight: isActive ? 600 : 400,
                          transition: "all 0.2s"
                        }}
                      >
                        <div style={{ width: 12, height: 12, borderRadius: 6, background: item.color, boxShadow: isActive ? `0 0 8px ${item.color}` : "none" }} />
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {mode === "patrol" && (
            <div style={{
              background: "rgba(10, 10, 10, 0.75)",
              backdropFilter: "blur(12px)",
              border: "1px solid rgba(139, 92, 246, 0.3)",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              width: "300px",
              boxShadow: "0 8px 32px rgba(139, 92, 246, 0.1)"
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                <span style={{ fontSize: "13px", color: "var(--text-primary)", fontWeight: 600 }}>Patrol Configuration</span>
              </div>

              {/* Toggle Switch */}
              <div style={{ display: "flex", background: "rgba(255,255,255,0.05)", borderRadius: "6px", padding: "4px" }}>
                <button
                  onClick={() => setAllocationMode("proportional")}
                  style={{
                    flex: 1, padding: "6px", fontSize: "11px", borderRadius: "4px", border: "none", cursor: "pointer",
                    background: allocationMode === "proportional" ? "rgba(139, 92, 246, 0.2)" : "transparent",
                    color: allocationMode === "proportional" ? "#a78bfa" : "var(--text-muted)",
                    fontWeight: allocationMode === "proportional" ? 600 : 400
                  }}
                >
                  Global Pool
                </button>
                <button
                  onClick={() => setAllocationMode("custom")}
                  style={{
                    flex: 1, padding: "6px", fontSize: "11px", borderRadius: "4px", border: "none", cursor: "pointer",
                    background: allocationMode === "custom" ? "rgba(139, 92, 246, 0.2)" : "transparent",
                    color: allocationMode === "custom" ? "#a78bfa" : "var(--text-muted)",
                    fontWeight: allocationMode === "custom" ? 600 : 400
                  }}
                >
                  Custom Per-Station
                </button>
              </div>

              {allocationMode === "proportional" ? (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>AVAILABLE OFFICERS</span>
                    <span style={{ fontSize: "12px", color: "#a78bfa", fontWeight: 600, background: "rgba(139, 92, 246, 0.15)", padding: "2px 6px", borderRadius: "4px" }}>
                      {numOfficers}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="500"
                    step="5"
                    value={numOfficers}
                    onChange={(e) => setNumOfficers(parseInt(e.target.value))}
                    aria-label={`Number of officers: ${numOfficers}`}
                    aria-valuetext={`${numOfficers} officers`}
                    style={{ width: "100%", accentColor: "#8b5cf6" }}
                  />
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "right" }}>
                    {isLoadingPatrol ? "Optimizing routes..." : "Auto-distributed to high risk"}
                  </div>
                </>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
                    Specify exactly how many officers to assign to individual stations. Stations with 0 are ignored.
                  </div>
                  <div style={{ maxHeight: "250px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px", paddingRight: "4px" }}>
                    {stationsList?.map((stn) => (
                      <div key={stn.station_name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(255,255,255,0.02)", padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--border)" }}>
                        <span style={{ fontSize: "12px", color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "160px" }} title={stn.station_name}>
                          {stn.station_name}
                        </span>
                        <input 
                          type="number"
                          min="0"
                          max="60"
                          value={customAlloc[stn.station_name] || 0}
                          onChange={(e) => {
                            const val = Math.min(60, Math.max(0, parseInt(e.target.value) || 0));
                            setCustomAlloc(prev => ({ ...prev, [stn.station_name]: val }));
                          }}
                          style={{
                            width: "50px", background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", borderRadius: "4px", padding: "4px", fontSize: "12px", textAlign: "center"
                          }}
                        />
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "right", marginTop: "4px", fontWeight: 600 }}>
                    Total Custom Pool: {Object.values(customAlloc).reduce((a, b) => a + b, 0)} officers
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Loading Indicator Overlay */}
      {isModeLoading && (
        <div style={{
          position: "absolute",
          top: 24, left: "50%", transform: "translateX(-50%)",
          background: "rgba(59, 130, 246, 0.9)",
          color: "#fff",
          padding: "8px 24px",
          borderRadius: "20px",
          fontSize: "13px",
          fontWeight: 600,
          zIndex: 20,
          boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)",
          animation: "pulse 2s infinite"
        }}>
          Computing spatial data...
        </div>
      )}

      <SegmentPanel
        segment={selectedSeg}
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
      />
    </div>
  );
}
