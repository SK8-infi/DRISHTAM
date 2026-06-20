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



  return (
    <>
      <div 
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 1000 }} 
        onClick={onClose}
        aria-hidden="true"
      />
      <div role="dialog" aria-label={`Station detail: ${stationName}`} aria-modal="true" style={{
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
          <button onClick={onClose} aria-label="Close station detail" style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "20px" }}>&times;</button>
        </div>

        {/* Content */}
        <div style={{ padding: "24px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "24px" }}>
          {loading || !detail ? (
            <div role="status" aria-live="polite" style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>Loading details...</div>
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
                {(() => {
                  const hp = detail.hourly_profile;
                  const values = Array.from({ length: 24 }, (_, h) => Number(hp[h.toString()] ?? hp[String(h)] ?? 0));
                  const maxVal = Math.max(1, ...values);
                  const barHeight = 80; // px
                  return (
                    <>
                      <div style={{ display: "flex", alignItems: "flex-end", height: `${barHeight}px`, gap: "2px" }}>
                        {values.map((val, h) => {
                          const px = Math.round((val / maxVal) * barHeight);
                          return (
                            <div key={h} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%", position: "relative" }} aria-label={`Hour ${h}: ${val} violations`} role="img">
                              <div style={{ width: "100%", height: `${px}px`, background: "var(--accent)", borderRadius: "2px 2px 0 0", opacity: px > barHeight * 0.8 ? 1 : 0.6 }} />
                            </div>
                          );
                        })}
                      </div>
                      <div style={{ display: "flex", marginTop: "4px" }}>
                        {values.map((_, h) => (
                          <div key={h} style={{ flex: 1, textAlign: "left" }}>
                            {h % 6 === 0 && <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{h}h</span>}
                          </div>
                        ))}
                      </div>
                    </>
                  );
                })()}
              </div>

              {/* Top Roads Table */}
              <div>
                <h4 style={{ margin: "0 0 16px 0", fontSize: "14px", color: "var(--text-muted)" }}>Top High-Risk Roads</h4>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col" style={{ width: "60%" }}>Road</th>
                      <th scope="col" style={{ textAlign: "right" }}>Count</th>
                      <th scope="col" style={{ textAlign: "right" }}>PIS</th>
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
