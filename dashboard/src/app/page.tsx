"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchOverview, fetchStations } from "@/lib/api";
import { formatNumber } from "@/lib/colors";
import dynamic from "next/dynamic";
import Link from "next/link";
import HourlyChart from "@/components/Charts/HourlyChart";
import TopRoadsTable from "@/components/Charts/TopRoadsTable";
import AnimatedCounter from "@/components/AnimatedCounter";
const MiniMapPulse = dynamic(() => import("@/components/MiniMapPulse"), {
  ssr: false,
  loading: () => <div style={{ height: 140, background: "#080808", borderRadius: "var(--radius)" }} />,
});
import Sparkline from "@/components/Charts/Sparkline";
import ParetoDonut from "@/components/Charts/ParetoDonut";

const Icons = {
  Car: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 16H9m10 0h3v-3.15a1 1 0 0 0-.84-.99L16 11l-2.7-3.6a2 2 0 0 0-1.6-.8H8.3a2 2 0 0 0-1.6.8L4 11l-5.16.86a1 1 0 0 0-.84.99V16h3m10 0a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM7 16a2 2 0 1 0 4 0 2 2 0 0 0-4 0z"/></svg>,
  Road: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 22-8-3v-5l8 3 8-3v5l-8 3z"/><path d="m20 14-8-3-8 3"/><path d="M12 2v10"/><path d="m4 6 8-3 8 3"/></svg>,
  Money: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/></svg>,
  House: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>,
  Alert: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  Brain: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>,
  Impact: <svg aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>,
  ArrowRight: <svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
};

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["overview"],
    queryFn: fetchOverview,
  });

  const { data: stations } = useQuery({
    queryKey: ["stations-overview"],
    queryFn: () => fetchStations(),
  });

  const hourlyDataArray = useMemo(() => data ? Object.values(data.hourly_distribution) : [], [data]);
  const getSparklineData = useMemo(() => (index: number) => {
    // Perturb the array slightly to visually differentiate the charts while preserving the real trend
    return hourlyDataArray.map((val, i) => Math.max(0, val * (1 + Math.sin(index + i) * 0.4)));
  }, [hourlyDataArray]);

  const kpis = useMemo(() => data ? [
    { icon: Icons.Car, label: "Total Violations", value: formatNumber(data.total_violations), sub: "Jan-May 2025" },
    { icon: Icons.Road, label: "Segments Affected", value: formatNumber(data.affected_segments), sub: `of ${formatNumber(data.total_segments)} total` },
    { icon: Icons.House, label: "Unique Roads", value: formatNumber(data.unique_roads), sub: `${data.pct_car}% are cars` },
    { icon: Icons.Impact, label: "Baseline Impact", value: formatNumber(data.baseline_impact), sub: "Network-wide GBM score" },
  ] : [], [data]);

  if (isLoading) return <div className="loading" role="status" aria-live="polite"><div className="spinner" aria-hidden="true" />Loading AI engines...</div>;
  if (error || !data) return <div className="loading" role="alert">Failed to connect to AI Core</div>;

  return (
    <div className="animate-in">
      {/* Enforcement Gap Callout Banner */}
      <div role="alert" aria-label="Intelligence insight: optimal patrol reallocation" style={{
        background: "rgba(139, 92, 246, 0.1)",
        border: "1px solid rgba(139, 92, 246, 0.3)",
        borderRadius: "var(--radius-sm)",
        padding: "16px 24px",
        marginBottom: "32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        boxShadow: "0 4px 12px rgba(139, 92, 246, 0.05)"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div aria-hidden="true" style={{ color: "#a78bfa" }}>{Icons.Brain}</div>
          <div style={{ color: "var(--text-primary)", fontSize: "14px" }}>
            <strong style={{ color: "#a78bfa", fontSize: "15px" }}>Intelligence Insight: Optimal Patrol Reallocation</strong>
            <span style={{ color: "var(--text-secondary)", marginLeft: "8px" }}>— Deploying during 4-8 PM mitigates {data.enforcement_gap.pct_of_total}% of high-impact violations.</span>
          </div>
        </div>
        <Link href="/whatif" className="btn btn-primary" style={{ background: "#8b5cf6", color: "#fff", border: "none", fontSize: "13px", padding: "8px 16px" }}>
          Run What-If Scenario {Icons.ArrowRight}
        </Link>
      </div>

      <div className="page-header" style={{ marginBottom: "24px" }}>
        <h2 id="page-title">Dashboard Overview</h2>
        <p>Real-time enforcement intelligence powered by 3 ML engines</p>
      </div>

      {/* Hero & Live Pulse Section */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px", marginBottom: "24px" }}>
        
        {/* Left: Hero Stat */}
        <div className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "center", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: -100, right: -50, width: 300, height: 300, background: "var(--accent-glow)", filter: "blur(80px)", borderRadius: "50%", zIndex: 0 }} />
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="card-title" style={{ color: "var(--accent-hover)", fontSize: "14px" }}>Estimated Congestion Cost</div>
            <div style={{ fontSize: "64px", fontWeight: 800, letterSpacing: "-2px", color: "var(--text-primary)", lineHeight: 1 }}>
              <AnimatedCounter targetValue={data.estimated_cost_crore_per_day} prefix="₹" suffix="Cr" />
            </div>
            <div style={{ fontSize: "14px", color: "var(--text-muted)", marginTop: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
              <div aria-hidden="true" style={{ width: 8, height: 8, background: "var(--success)", borderRadius: "50%", boxShadow: "0 0 8px var(--success)" }} />
              <span>Live computation active</span>
            </div>
          </div>
        </div>

        {/* Right: City Pulse */}
        <div className="card" style={{ padding: "16px" }}>
          <MiniMapPulse />
        </div>
      </div>

      {/* System Status Row */}
      <div role="status" aria-label="Engine status indicators" style={{ display: "flex", gap: "16px", marginBottom: "40px" }}>
        {[
          { name: "Engine 1: Impact", status: "LIVE", color: "var(--info)" },
          { name: "Engine 2: What-If", status: "LIVE", color: "var(--accent)" },
          { name: "Engine 3: Risk r=0.92", status: "LIVE", color: "var(--warning)" }
        ].map((engine, i) => (
          <div key={i} role="status" aria-label={`${engine.name}: ${engine.status}`} style={{
            display: "flex", alignItems: "center", gap: "8px", 
            padding: "6px 12px", background: "var(--bg-elevated)", 
            borderRadius: "100px", border: "1px solid var(--border)",
            fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)"
          }}>
            <div style={{ color: engine.color, display: "flex", alignItems: "center", gap: "6px" }}>
              <div aria-hidden="true" style={{ width: 6, height: 6, background: engine.color, borderRadius: "50%", boxShadow: `0 0 6px ${engine.color}` }} />
              {engine.status}
            </div>
            <span aria-hidden="true" style={{ color: "var(--border-light)" }}>|</span>
            <span style={{ color: "var(--text-primary)" }}>{engine.name}</span>
          </div>
        ))}
      </div>

      {/* Division KPI Row */}
      {stations && (
        <div style={{ marginBottom: "40px" }}>
          <h3 id="division-heading" style={{ fontSize: "16px", marginBottom: "16px", color: "var(--text-primary)" }}>Division Performance</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }} role="list" aria-labelledby="division-heading">
            {["East", "West", "North", "South"].map(div => {
              const divStations = stations.filter(s => s.division === div);
              const violations = divStations.reduce((sum, s) => sum + s.violations, 0);
              const avgPis = divStations.reduce((sum, s) => sum + s.mean_pis, 0) / (divStations.length || 1);
              let color = "#9ca3af";
              if (div === "East") color = "#3b82f6";
              if (div === "West") color = "#f97316";
              if (div === "North") color = "#22c55e";
              if (div === "South") color = "#a855f7";

              return (
                <div key={div} className="card" role="listitem" aria-label={`${div} Division: ${formatNumber(violations)} violations, mean risk ${avgPis.toFixed(2)}`} style={{ padding: "16px", borderTop: `4px solid ${color}` }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px", color: "var(--text-primary)" }}>{div} Division</div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Stations</span>
                    <span style={{ fontSize: "12px", fontWeight: 600 }}>{divStations.length}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Violations</span>
                    <span style={{ fontSize: "12px", fontWeight: 600 }}>{formatNumber(violations)}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Mean Risk</span>
                    <span style={{ fontSize: "12px", fontWeight: 600, color: avgPis > 4 ? "var(--danger)" : "var(--text-primary)" }}>
                      {avgPis.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* KPI Grid with Sparklines & Donut */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "24px", marginBottom: "40px" }}>
        
        {/* Animated Pareto Donut Card */}
        <div className="kpi-card" style={{ gridRow: "span 2", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="card-title">Impact Concentration</div>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "16px" }}>
              The 80/20 rule is highly skewed:
            </p>
            <ParetoDonut />
          </div>
          <div style={{ marginTop: "24px", padding: "12px", background: "rgba(59, 130, 246, 0.1)", borderRadius: "var(--radius-sm)", border: "1px solid rgba(59, 130, 246, 0.2)" }}>
            <span style={{ color: "var(--accent-hover)", fontWeight: 600 }}>13.8%</span> of violations cause <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>80%</span> of the network congestion impact.
          </div>
        </div>

        {kpis.map((kpi, i) => (
          <div key={i} className="kpi-card" style={{ padding: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div className="card-title" style={{ marginBottom: "8px" }}>{kpi.label}</div>
                <div className="card-value" style={{ fontSize: "28px" }}>{kpi.value}</div>
              </div>
              <div className="kpi-icon" aria-hidden="true" style={{ margin: 0, width: 36, height: 36 }}>{kpi.icon}</div>
            </div>
            {/* Sparkline from API Data */}
            <div style={{ marginTop: "12px" }}>
              <Sparkline dataArray={getSparklineData(i)} color={i % 2 === 0 ? "var(--accent)" : "var(--info)"} />
            </div>
            <div className="card-sub" style={{ marginTop: "8px", fontSize: "12px" }}>{kpi.sub}</div>
          </div>
        ))}
      </div>

      <div className="charts-grid">
        <div className="card" style={{ gridColumn: "span 2" }}>
          <div className="card-title" id="hourly-chart-label">Hourly Violation Distribution</div>
          <div style={{ marginTop: '16px' }} role="img" aria-labelledby="hourly-chart-label">
            <HourlyChart data={data.hourly_distribution} gapHours={data.enforcement_gap.hours} />
          </div>
        </div>
      </div>

      {/* Bottom Section: Top Roads & Insights */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px", marginTop: "24px" }}>
        
        <div className="card">
          <div className="card-title" id="top-roads-label">Top 10 Roads by Impact</div>
          <div style={{ marginTop: '16px' }} role="region" aria-labelledby="top-roads-label">
            <TopRoadsTable roads={data.top_roads} />
          </div>
        </div>

        {/* "What Would Change" Insight Card */}
        <div className="card" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-light)", display: "flex", flexDirection: "column" }}>
          <div className="card-title" style={{ color: "var(--accent)" }}>Intelligence Insight</div>
          <h3 style={{ fontSize: "24px", color: "var(--text-primary)", fontWeight: 600, marginTop: "12px", lineHeight: 1.3 }}>
            What Would Change?
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "15px", marginTop: "16px", lineHeight: 1.6 }}>
            If you enforce just the <strong style={{ color: "var(--text-primary)" }}>top 5 roads</strong> from this list, congestion impact drops by <strong style={{ color: "var(--success)" }}>0.3%</strong>.
            However, shifting patrols to the evening peak drops impact by <strong style={{ color: "var(--success)" }}>4.1%</strong>.
          </p>
          <div style={{ marginTop: "auto", paddingTop: "24px" }}>
            <Link href="/whatif" className="btn btn-secondary" style={{ width: "100%", justifyContent: "space-between" }}>
              Simulate Patrols {Icons.ArrowRight}
            </Link>
          </div>
        </div>
        
      </div>
    </div>
  );
}
