"use client";

import { useEffect, useState } from "react";
import { StationDetail, fetchStationDetail } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function StationPanel({ stationName, onClose }: { stationName: string; onClose: () => void }) {
  const [detail, setDetail] = useState<StationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    setLoading(true);
    fetchStationDetail(stationName)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [stationName]);

  const maxProfile = detail ? Math.max(...Object.values(detail.hourly_profile)) : 1;

  return (
    <>
      <div 
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 1000 }} 
        onClick={onClose} 
      />
      <div style={{
        position: "fixed",
        top: 0, right: 0, bottom: 0,
        width: "450px",
        background: "var(--bg-card)",
        borderLeft: "1px solid var(--border)",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.5)",
        zIndex: 1001,
        display: "flex",
        flexDirection: "column",
        transform: "translateX(0)",
        transition: "transform 0.3s ease"
      }}>
        {/* Header */}
        <div style={{ padding: "24px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2 style={{ margin: "0 0 8px 0", fontSize: "20px" }}>{stationName}</h2>
            <span style={{ fontSize: "12px", color: "var(--accent)", padding: "2px 8px", background: "rgba(59,130,246,0.1)", borderRadius: "10px" }}>
              {detail?.division || "Loading..."} Division
            </span>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "20px" }}>&times;</button>
        </div>

        {/* Content */}
        <div style={{ padding: "24px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "24px" }}>
          {loading || !detail ? (
            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>Loading details...</div>
          ) : (
            <>
              {/* KPIs */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="card" style={{ padding: "16px", background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Total Violations</div>
                  <div style={{ fontSize: "20px", fontWeight: 600 }}>{detail.violations.toLocaleString()}</div>
                </div>
                <div className="card" style={{ padding: "16px", background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Mean PIS</div>
                  <div style={{ fontSize: "20px", fontWeight: 600, color: "var(--danger)" }}>{detail.mean_pis.toFixed(1)}</div>
                </div>
              </div>

              {/* Hourly Profile */}
              <div>
                <h4 style={{ margin: "0 0 16px 0", fontSize: "14px", color: "var(--text-muted)" }}>24H Violation Profile</h4>
                <div style={{ display: "flex", alignItems: "flex-end", height: "80px", gap: "2px" }}>
                  {Array.from({ length: 24 }).map((_, h) => {
                    const val = detail.hourly_profile[h.toString()] || 0;
                    const pct = (val / maxProfile) * 100;
                    return (
                      <div key={h} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", position: "relative" }} title={`Hour ${h}: ${val}`}>
                        <div style={{ width: "100%", height: `${pct}%`, background: "var(--accent)", borderRadius: "2px 2px 0 0", opacity: pct > 80 ? 1 : 0.6 }} />
                        {h % 6 === 0 && <span style={{ position: "absolute", bottom: "-20px", fontSize: "10px", color: "var(--text-muted)", left: 0 }}>{h}h</span>}
                      </div>
                    );
                  })}
                </div>
                <div style={{ height: "20px" }} />
              </div>

              {/* Top Roads Table */}
              <div>
                <h4 style={{ margin: "0 0 16px 0", fontSize: "14px", color: "var(--text-muted)" }}>Top High-Risk Roads</h4>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: "60%" }}>Road</th>
                      <th style={{ textAlign: "right" }}>Count</th>
                      <th style={{ textAlign: "right" }}>PIS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.top_roads.map((r, i) => (
                      <tr key={i}>
                        <td style={{ fontSize: "13px" }}>{r.road_name}</td>
                        <td style={{ textAlign: "right", fontSize: "13px" }}>{r.violations.toLocaleString()}</td>
                        <td style={{ textAlign: "right", fontSize: "13px", color: r.mean_pis > 4 ? "var(--danger)" : "inherit" }}>
                          {r.mean_pis.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

            </>
          )}
        </div>

        {/* Footer Action */}
        <div style={{ padding: "24px", borderTop: "1px solid var(--border)" }}>
          <button 
            className="btn-primary" 
            style={{ width: "100%", padding: "12px", justifyContent: "center" }}
            onClick={() => router.push(`/whatif?station=${encodeURIComponent(stationName)}`)}
            disabled={loading}
          >
            Optimize Patrol for {stationName}
          </button>
        </div>
      </div>
    </>
  );
}
