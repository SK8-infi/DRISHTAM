"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchClusterDetail } from "@/lib/api";
import { formatNumber } from "@/lib/colors";
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from "recharts";
import { useRouter } from "next/navigation";

interface Props {
  clusterId: number | null;
  open: boolean;
  onClose: () => void;
}

export default function ClusterPanel({ clusterId, open, onClose }: Props) {
  const router = useRouter();

  const { data: detail, isLoading } = useQuery({
    queryKey: ["clusterDetail", clusterId],
    queryFn: () => fetchClusterDetail(clusterId!),
    enabled: !!clusterId && open,
  });

  const handleWhatIf = () => {
    if (!detail) return;
    const roadsStr = encodeURIComponent(detail.road_names.join(","));
    router.push(`/whatif?roads=${roadsStr}`);
  };

  const hourlyData = detail ? Object.entries(detail.hourly_profile).map(([hour, count]) => ({
    hour: `${hour.padStart(2, '0')}:00`,
    count
  })) : [];

  return (
    <div className={`segment-panel ${open ? "open" : ""}`}>
      <div className="segment-panel-header">
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
            Cluster #{clusterId}
          </h3>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {detail?.n_violations || 0} violations · {detail?.radius_m.toFixed(0) || 0}m radius
          </p>
        </div>
        <button className="segment-panel-close" onClick={onClose}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      {isLoading && (
        <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "12px" }}>
          Loading cluster details...
        </div>
      )}

      {detail && (
        <>
          {/* Key Metrics */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div style={{ background: "var(--bg-elevated)", padding: "12px", borderRadius: "8px" }}>
              <div style={{ fontSize: "10px", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "0.5px", marginBottom: "4px" }}>MEAN SEVERITY</div>
              <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--danger)" }}>{detail.mean_pis.toFixed(1)} PIS</div>
            </div>
            <div style={{ background: "var(--bg-elevated)", padding: "12px", borderRadius: "8px" }}>
              <div style={{ fontSize: "10px", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "0.5px", marginBottom: "4px" }}>CAPACITY BLOCKED</div>
              <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--warning)" }}>{(detail.mean_capacity_blocked * 100).toFixed(1)}%</div>
            </div>
          </div>

          {/* Hourly Profile */}
          <div className="segment-section">
            <h4>Hourly Violation Profile</h4>
            <div style={{ height: 120, width: "100%", marginTop: 8 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourlyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <XAxis dataKey="hour" tick={{ fontSize: 9, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
                  <RechartsTooltip
                    cursor={{ fill: "rgba(255,255,255,0.05)" }}
                    contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", fontSize: "12px" }}
                    labelStyle={{ color: "var(--text-muted)", marginBottom: "4px" }}
                  />
                  <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                    {hourlyData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill="var(--accent)" />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Roads Breakdown */}
          <div className="segment-section">
            <h4>Top Roads in Cluster</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "160px", overflowY: "auto", paddingRight: "4px" }}>
              {detail.road_breakdown.map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(255,255,255,0.02)", padding: "8px 12px", borderRadius: "6px" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {r.road_name}
                    </div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>
                      {formatNumber(r.violations)} violations
                    </div>
                  </div>
                  <div style={{ textAlign: "right", marginLeft: "12px" }}>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--warning)" }}>
                      {r.mean_pis.toFixed(1)}
                    </div>
                    <div style={{ fontSize: "9px", color: "var(--text-muted)" }}>Mean PIS</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Vehicle Types */}
          <div className="segment-section">
            <h4>Vehicle Composition</h4>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {Object.entries(detail.vehicle_types).map(([type, count], i) => (
                <div key={i} style={{ fontSize: "11px", background: "var(--bg-elevated)", padding: "4px 8px", borderRadius: "4px", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                  {type}: <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{formatNumber(count)}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ flex: 1 }} />

          {/* Actions */}
          <div style={{ display: "flex", gap: 8, marginTop: "8px" }}>
            <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleWhatIf}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              What-If: Enforce Cluster
            </button>
          </div>
        </>
      )}
    </div>
  );
}
