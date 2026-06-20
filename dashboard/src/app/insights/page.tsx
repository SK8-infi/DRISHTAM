"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchInsights, type Insight, type DataQuality, type Experiment } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

/* ── Icons ──────────────────────────────────────────────── */
const Icons = {
  impact: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>,
  enforcement: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  risk: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>,
  bias: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>,
  arrowRight: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
};

function getSeverityColor(severity: string) {
  switch (severity) {
    case "critical": return "var(--danger)";
    case "warning": return "var(--warning)";
    case "success": return "var(--success)";
    default: return "var(--info)";
  }
}

export default function InsightsPage() {
  const router = useRouter();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ["insights"],
    queryFn: fetchInsights,
  });

  if (isLoading) return <div className="loading"><div className="spinner" />Loading dynamic insights...</div>;
  if (error || !data) return <div className="loading" style={{ color: "var(--danger)" }}>Failed to load insights.</div>;

  const { findings, data_quality, experiments, methodology } = data;

  return (
    <div className="animate-in" style={{ position: "relative" }}>
      {/* Background ambient glows */}
      <div style={{ position: "absolute", top: -100, left: -100, width: 400, height: 400, background: "var(--accent-glow)", filter: "blur(120px)", borderRadius: "50%", zIndex: 0, pointerEvents: "none" }} />
      <div style={{ position: "absolute", top: 400, right: -100, width: 300, height: 300, background: "rgba(139, 92, 246, 0.15)", filter: "blur(100px)", borderRadius: "50%", zIndex: 0, pointerEvents: "none" }} />

      <div className="page-header" style={{ position: "relative", zIndex: 1, marginBottom: "32px" }}>
        <h2>💡 Executive Insights</h2>
        <p>Live, data-driven discoveries from the DRISHTAM enforcement engines.</p>
      </div>

      {/* ── 1. Evidence Cards ───────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "24px", marginBottom: "48px", position: "relative", zIndex: 1 }}>
        {findings.map((finding: Insight, i: number) => {
          const color = getSeverityColor(finding.severity);
          
          return (
            <div key={finding.id} className="card animate-in" style={{ 
              animationDelay: `${i * 50}ms`, 
              borderLeft: `3px solid ${color}`, 
              display: "flex", 
              flexDirection: "column",
              background: "rgba(12, 12, 14, 0.6)",
              backdropFilter: "blur(12px)",
              position: "relative",
              overflow: "hidden"
            }}>
              {/* Subtle radial glow inside card based on severity */}
              <div style={{ position: "absolute", top: 0, right: 0, width: "150px", height: "150px", background: color, opacity: 0.05, filter: "blur(40px)", borderRadius: "50%", pointerEvents: "none" }} />

              <div style={{ display: "flex", gap: "24px", flex: 1, position: "relative", zIndex: 1 }}>
                
                {/* Hero Metric */}
                <div style={{ minWidth: "130px", display: "flex", flexDirection: "column", justifyContent: "flex-start" }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "1px", textTransform: "uppercase", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ color }}>{Icons[finding.category as keyof typeof Icons] || Icons.impact}</span>
                    {finding.category}
                  </div>
                  <div style={{ fontSize: "38px", fontWeight: 800, color: "var(--text-primary)", lineHeight: 1, letterSpacing: "-1.5px" }}>
                    {finding.value}
                  </div>
                </div>

                {/* Explanation */}
                <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                  <h3 style={{ fontSize: "17px", fontWeight: 700, marginBottom: "8px", color: "var(--text-primary)", lineHeight: 1.3 }}>{finding.title}</h3>
                  <p style={{ fontSize: "14px", color: "var(--text-secondary)", lineHeight: 1.6, flex: 1 }}>{finding.detail}</p>
                  
                  {/* Action Link */}
                  {finding.link_page && (
                    <div style={{ marginTop: "20px" }}>
                      <Link 
                        href={`${finding.link_page}${finding.link_params ? '?' + finding.link_params : ''}`}
                        className="btn btn-secondary"
                        style={{ display: "inline-flex", padding: "8px 16px", fontSize: "13px", color: color, borderColor: "rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)" }}
                      >
                        See Evidence {Icons.arrowRight}
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── 2. Methodology Timeline ─────────────────────────────── */}
      <div style={{ position: "relative", zIndex: 1, marginBottom: "48px" }}>
        <h3 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "20px", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ width: 8, height: 8, background: "var(--accent)", borderRadius: "50%", boxShadow: "0 0 8px var(--accent)" }} />
          System Pipeline Architecture
        </h3>
        
        <div className="card" style={{ overflowX: "auto", background: "rgba(8, 8, 10, 0.6)", backdropFilter: "blur(12px)", padding: "32px 24px" }}>
          <div style={{ display: "flex", alignItems: "stretch", gap: "20px", minWidth: "900px" }}>
            
            {/* Node 1 */}
            <div style={{ flex: 1, background: "rgba(59, 130, 246, 0.05)", border: "1px solid rgba(59, 130, 246, 0.2)", borderRadius: "12px", padding: "20px", position: "relative" }}>
              <div style={{ position: "absolute", top: "-1px", left: "20%", right: "20%", height: "2px", background: "linear-gradient(90deg, transparent, var(--accent), transparent)" }} />
              <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--accent)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "1px" }}>1. Raw Data Layer</div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.6 }}>{methodology.data.split(",")[0]}</div>
            </div>
            
            <div style={{ color: "var(--border)", display: "flex", alignItems: "center" }}>{Icons.arrowRight}</div>

            {/* Node 2 */}
            <div style={{ flex: 1, background: "rgba(139, 92, 246, 0.05)", border: "1px solid rgba(139, 92, 246, 0.2)", borderRadius: "12px", padding: "20px", position: "relative" }}>
              <div style={{ position: "absolute", top: "-1px", left: "20%", right: "20%", height: "2px", background: "linear-gradient(90deg, transparent, #8b5cf6, transparent)" }} />
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#8b5cf6", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "1px" }}>2. Spatial Engine</div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.6 }}>{methodology.clusters.split(".")[0]}</div>
            </div>

            <div style={{ color: "var(--border)", display: "flex", alignItems: "center" }}>{Icons.arrowRight}</div>

            {/* Node 3 */}
            <div style={{ flex: 1, background: "rgba(249, 115, 22, 0.05)", border: "1px solid rgba(249, 115, 22, 0.2)", borderRadius: "12px", padding: "20px", position: "relative" }}>
              <div style={{ position: "absolute", top: "-1px", left: "20%", right: "20%", height: "2px", background: "linear-gradient(90deg, transparent, var(--warning), transparent)" }} />
              <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--warning)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "1px" }}>3. Impact Engine</div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.6 }}>Digital Twin PIS (r=0.59)</div>
            </div>

            <div style={{ color: "var(--border)", display: "flex", alignItems: "center" }}>{Icons.arrowRight}</div>

            {/* Node 4 */}
            <div style={{ flex: 1, background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: "12px", padding: "20px", position: "relative" }}>
              <div style={{ position: "absolute", top: "-1px", left: "20%", right: "20%", height: "2px", background: "linear-gradient(90deg, transparent, var(--success), transparent)" }} />
              <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--success)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "1px" }}>4. Risk Forecaster</div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.6 }}>{methodology.engine_3.split(".")[0]}</div>
            </div>

          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "32px", position: "relative", zIndex: 1 }}>
        
        {/* ── 3. Data Quality Scorecard ─────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <h3 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "20px", color: "var(--text-primary)" }}>Data Health</h3>
          <div className="card" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", padding: "24px", background: "rgba(12, 12, 14, 0.6)", backdropFilter: "blur(12px)", flex: 1 }}>
            {[
              { label: "Coverage", value: `${data_quality.road_coverage_pct}%`, color: "var(--text-primary)" },
              { label: "Missing Names", value: `${data_quality.missing_road_names_pct}%`, color: data_quality.missing_road_names_pct < 5 ? "var(--success)" : "var(--warning)" },
              { label: "Violations", value: data_quality.total_records.toLocaleString(), color: "var(--text-primary)" },
              { label: "Segments", value: data_quality.segments_total.toLocaleString(), color: "var(--text-primary)" },
              { label: "Hours Covered", value: `${data_quality.hours_covered}/24`, color: "var(--text-primary)" },
              { label: "Engineered Features", value: data_quality.features_count, color: "var(--accent)" },
            ].map((metric, idx) => (
              <div key={idx}>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px", fontWeight: 600 }}>{metric.label}</div>
                <div style={{ fontSize: "24px", fontWeight: 800, color: metric.color }}>{metric.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── 4. Experiment Log ─────────────────────────────────── */}
        <div>
          <h3 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "20px", color: "var(--text-primary)" }}>ML Experiment Log</h3>
          <div className="card table-container" style={{ padding: 0, background: "rgba(12, 12, 14, 0.6)", backdropFilter: "blur(12px)", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "rgba(255,255,255,0.03)", borderBottom: "1px solid var(--border)" }}>
                  <th style={{ padding: "16px 20px", textAlign: "left", fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "1px" }}>MODEL ARCHITECTURE</th>
                  <th style={{ padding: "16px 20px", textAlign: "left", fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "1px" }}>TYPE</th>
                  <th style={{ padding: "16px 20px", textAlign: "right", fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "1px" }}>FEATURES</th>
                  <th style={{ padding: "16px 20px", textAlign: "right", fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "1px" }}>SCORE (r)</th>
                </tr>
              </thead>
              <tbody>
                {experiments.sort((a, b) => b.score - a.score).map((exp, i) => (
                  <tr key={i} style={{ 
                    borderBottom: i < experiments.length - 1 ? "1px solid var(--border)" : "none", 
                    background: i === 0 ? "rgba(59, 130, 246, 0.08)" : "transparent" 
                  }}>
                    <td style={{ padding: "16px 20px", fontSize: "14px", fontWeight: i === 0 ? 700 : 500, color: i === 0 ? "var(--accent)" : "var(--text-primary)" }}>
                      {exp.name} {i === 0 && <span style={{ marginLeft: 8, fontSize: 16 }}>🏆</span>}
                    </td>
                    <td style={{ padding: "16px 20px", fontSize: "13px", color: "var(--text-secondary)" }}>{exp.model_type}</td>
                    <td style={{ padding: "16px 20px", textAlign: "right", fontSize: "13px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{exp.features}</td>
                    <td style={{ padding: "16px 20px", textAlign: "right", fontSize: "14px", fontWeight: 700, fontFamily: "var(--font-mono)", color: exp.score > 0.9 ? "var(--success)" : "var(--text-primary)" }}>
                      {exp.score.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
