"use client";

import { type SegmentDetail } from "@/lib/api";
import { impactToColor, tierLabel } from "@/lib/colors";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface Props {
  segment: SegmentDetail | null;
  open: boolean;
  onClose: () => void;
  onSwitchToRisk?: () => void;
}

export default function SegmentPanel({ segment, open, onClose, onSwitchToRisk }: Props) {
  if (!segment) return null;

  const hourlyData = Array.from({ length: 24 }, (_, h) => ({
    hour: h.toString().padStart(2, "0"),
    violations: segment.hourly_profile?.[h] || 0,
  }));

  const pisItems = segment.pis_breakdown
    ? [
        { label: "Capacity", value: segment.pis_breakdown.capacity },
        { label: "Importance", value: segment.pis_breakdown.importance },
        { label: "Junction", value: segment.pis_breakdown.junction },
        { label: "Temporal", value: segment.pis_breakdown.temporal },
        { label: "Density", value: segment.pis_breakdown.density },
        { label: "Severity", value: segment.pis_breakdown.severity },
      ]
    : [];

  return (
    <div className={`segment-panel ${open ? "open" : ""}`} role="dialog" aria-label={`Segment detail: ${segment.road_name || 'Unnamed'}`} aria-modal="false">
      <div className="segment-panel-header">
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
            <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 2l2 18"/><path d="M19 2l-2 18"/><path d="M12 6v2"/><path d="M12 12v2"/><path d="M12 18v2"/></svg>
            {segment.road_name || "Unnamed Segment"}
          </h3>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            Segment #{segment.seg_idx} · {tierLabel(segment.tier)} · {segment.lanes} lanes · {segment.length_m.toFixed(0)}m
          </p>
        </div>
        <button className="segment-panel-close" onClick={onClose} aria-label="Close segment detail panel">✕</button>
      </div>

      {/* Impact Score */}
      <div className="segment-section">
        <h4>Impact Score</h4>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              fontSize: 36,
              fontWeight: 800,
              fontFamily: "var(--font-mono)",
              color: impactToColor(segment.impact_gbm),
            }}
          >
            {segment.impact_gbm.toFixed(3)}
          </div>
          <div style={{ flex: 1 }}>
            <div className="impact-bar" style={{ height: 10 }} role="meter" aria-label="Impact score" aria-valuenow={Math.round(segment.impact_gbm * 100)} aria-valuemin={0} aria-valuemax={100}>
              <div
                className="impact-bar-fill"
                style={{
                  width: `${Math.min(segment.impact_gbm * 100, 100)}%`,
                  background: `linear-gradient(90deg, #22c55e, ${impactToColor(segment.impact_gbm)})`,
                }}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
              <span>0</span>
              <span>1.0</span>
            </div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6 }}>
          Betweenness: {segment.betweenness.toFixed(4)} · Violations: {segment.violation_count}
        </div>
      </div>

      {/* PIS Breakdown */}
      {pisItems.length > 0 && (
        <div className="segment-section">
          <h4>PIS Breakdown (Score: {segment.pis_breakdown?.overall.toFixed(1)})</h4>
          {pisItems.map((item) => (
            <div key={item.label} style={{ marginBottom: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 }}>
                <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                  {item.value.toFixed(3)}
                </span>
              </div>
              <div className="impact-bar" role="meter" aria-label={`${item.label} score`} aria-valuenow={Math.round(item.value * 100)} aria-valuemin={0} aria-valuemax={100}>
                <div
                  className="impact-bar-fill"
                  style={{
                    width: `${Math.min(item.value * 100, 100)}%`,
                    background: "var(--accent)",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Hourly Profile */}
      <div className="segment-section">
        <h4>Hourly Violations</h4>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={hourlyData} margin={{ top: 4, right: 4, bottom: 0, left: -30 }}>
            <XAxis dataKey="hour" tick={{ fill: "#64748b", fontSize: 9 }} tickLine={false} interval={3} />
            <YAxis tick={{ fill: "#64748b", fontSize: 9 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: "#1a2236", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }}
            />
            <Bar dataKey="violations" radius={[2, 2, 0, 0]}>
              {hourlyData.map((_, i) => (
                <Cell key={i} fill="#3b82f6" fillOpacity={0.7} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Neighbors */}
      {segment.neighbors.length > 0 && (
        <div className="segment-section">
          <h4>Connected Segments ({segment.neighbors.length})</h4>
          <div style={{ maxHeight: 150, overflowY: "auto" }}>
            {segment.neighbors.map((n, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "6px 0",
                  borderBottom: "1px solid var(--border)",
                  fontSize: 12,
                }}
              >
                <span style={{ color: "var(--text-secondary)" }}>#{n.seg_idx}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    color: impactToColor(n.impact_gbm),
                  }}
                >
                  {n.impact_gbm.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn btn-primary"
          style={{ flex: 1 }}
          aria-label={`Run What-If enforcement on ${segment.road_name || 'this segment'}`}
          onClick={() => {
            const road = encodeURIComponent(segment.road_name || "");
            window.location.href = `/whatif?road=${road}`;
          }}
        >
          <svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          What-If: Enforce
        </button>
        <button
          className="btn btn-secondary"
          style={{ flex: 1 }}
          aria-label={`View risk profile for ${segment.road_name || 'this segment'}`}
          onClick={() => {
            if (onSwitchToRisk) onSwitchToRisk();
          }}
        >
          <svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          Risk Profile
        </button>
      </div>
    </div>
  );
}
