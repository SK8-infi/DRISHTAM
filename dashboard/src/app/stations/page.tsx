"use client";

import { useEffect, useState, useCallback } from "react";
import { StationSummary, fetchStations } from "@/lib/api";
import StationPanel from "@/components/Stations/StationPanel";
import dynamic from "next/dynamic";

const StationBoundaryMap = dynamic(() => import("@/components/Stations/StationBoundaryMap"), { ssr: false });

const DIVISIONS = ["All", "East", "West", "North", "South"];

export default function StationsPage() {
  const [stations, setStations] = useState<StationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [division, setDivision] = useState("All");
  const [selectedStation, setSelectedStation] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchStations(division === "All" ? undefined : division)
      .then(setStations)
      .finally(() => setLoading(false));
  }, [division]);

  const handleStationClick = useCallback((name: string) => {
    setSelectedStation(name);
  }, []);

  return (
    <div style={{ display: "flex", height: "calc(100vh - 56px)", overflow: "hidden" }}>
      {/* ── Left Sidebar (List View) ── */}
      <div style={{ 
        width: "420px", 
        display: "flex", 
        flexDirection: "column", 
        borderRight: "1px solid var(--border)",
        background: "var(--bg-primary)",
        zIndex: 10,
        boxShadow: "4px 0 24px rgba(0,0,0,0.1)"
      }}>
        {/* Header */}
        <div style={{ padding: "24px", borderBottom: "1px solid var(--border)" }}>
          <h2 style={{ margin: "0 0 8px 0", fontSize: "22px", color: "var(--text-primary)" }}>Station Explorer</h2>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
            Analyze performance, resources, and jurisdiction boundaries across {division === "All" ? 54 : stations.length} traffic police stations.
          </p>
        </div>

        {/* Filters */}
        <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)", display: "flex", gap: "8px", overflowX: "auto" }}>
          {DIVISIONS.map((div) => (
            <button
              key={div}
              onClick={() => {
                setDivision(div);
                setSelectedStation(null); // Reset selection on filter change
              }}
              style={{
                padding: "6px 14px",
                borderRadius: "20px",
                border: "1px solid",
                borderColor: division === div ? "var(--accent)" : "var(--border)",
                background: division === div ? "rgba(59, 130, 246, 0.1)" : "var(--bg-elevated)",
                color: division === div ? "#fff" : "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.2s ease",
                fontSize: "12px",
                fontWeight: division === div ? 600 : 500,
                flexShrink: 0,
              }}
            >
              {div}
            </button>
          ))}
        </div>

        {/* Station Cards List */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
          {loading ? (
            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)", fontSize: "14px" }}>
              <div className="spinner" style={{ margin: "0 auto 16px auto" }} />
              Loading stations...
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {stations.map((stn) => {
                const isSelected = selectedStation === stn.station_name;
                const divColor = getDivisionColor(stn.division);
                
                return (
                  <div
                    key={stn.station_name}
                    className="card"
                    onClick={() => handleStationClick(stn.station_name)}
                    style={{
                      padding: "16px",
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                      borderTop: isSelected ? `1px solid ${divColor}` : "1px solid var(--border)",
                      borderRight: isSelected ? `1px solid ${divColor}` : "1px solid var(--border)",
                      borderBottom: isSelected ? `1px solid ${divColor}` : "1px solid var(--border)",
                      borderLeft: `4px solid ${divColor}`,
                      background: isSelected ? `rgba(${hexToRgb(divColor)}, 0.05)` : "var(--bg-elevated)",
                      transform: isSelected ? "translateX(4px)" : "none",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                      <h3 style={{ fontSize: "15px", margin: 0, fontWeight: 600, color: isSelected ? divColor : "var(--text-primary)" }}>
                        {stn.station_name}
                      </h3>
                      <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "10px", background: "rgba(255,255,255,0.05)", color: divColor, fontWeight: 600 }}>
                        {stn.division}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                      <div>
                        <div style={{ color: "var(--text-muted)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px" }}>Violations</div>
                        <div style={{ fontWeight: 600 }}>{stn.violations.toLocaleString()}</div>
                      </div>
                      <div>
                        <div style={{ color: "var(--text-muted)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px" }}>Mean Risk</div>
                        <div style={{ fontWeight: 600, color: stn.mean_pis > 4 ? "var(--danger)" : "var(--text-primary)" }}>{stn.mean_pis.toFixed(1)}</div>
                      </div>
                      <div>
                        <div style={{ color: "var(--text-muted)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px" }}>Roads</div>
                        <div style={{ fontWeight: 600 }}>{stn.roads}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Right Main Area (Map View) ── */}
      <div style={{ flex: 1, position: "relative" }}>
        {!loading && (
          <StationBoundaryMap 
            stations={stations} 
            selectedStation={selectedStation} 
            onStationClick={handleStationClick} 
          />
        )}
      </div>

      {/* ── Drilldown Overlay ── */}
      {selectedStation && (
        <StationPanel
          stationName={selectedStation}
          onClose={() => setSelectedStation(null)}
        />
      )}
    </div>
  );
}

function getDivisionColor(division: string) {
  switch (division) {
    case "East": return "#3b82f6";   // blue
    case "West": return "#f97316";   // orange
    case "North": return "#22c55e";  // green
    case "South": return "#a855f7";  // purple
    default: return "#9ca3af";
  }
}

function hexToRgb(hex: string) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? 
    `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` 
    : "255, 255, 255";
}
