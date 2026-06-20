"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchClusters } from "@/lib/api";
import { formatNumber } from "@/lib/colors";
import dynamic from "next/dynamic";
import ClusterPanel from "@/components/Map/ClusterPanel";

const ClusterBubbleMap = dynamic(() => import("@/components/Map/ClusterBubbleMap"), { ssr: false });

export default function ClustersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["clusters"],
    queryFn: () => fetchClusters(50),
  });

  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);

  if (isLoading) return <div className="loading" role="status" aria-live="polite"><div className="spinner" aria-hidden="true" />Loading clusters...</div>;

  const clusters = data?.clusters || [];
  
  // Get top 5 clusters
  const topClusters = clusters.slice(0, 5);

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
            <span style={{ color: "var(--accent)" }}>
              <svg aria-hidden="true" focusable="false" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
            </span>
            Cluster Explorer
          </h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
            {clusters.length} violation hotspot clusters detected via HDBSCAN
          </p>
        </div>
        
        {/* Key metrics header */}
        <div style={{ display: "flex", gap: "24px" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px" }}>TOTAL VIOLATIONS</div>
            <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)" }}>{formatNumber(clusters.reduce((s, c) => s + c.n_violations, 0))}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px" }}>TOTAL IMPACT</div>
            <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--danger)" }}>{formatNumber(clusters.reduce((s, c) => s + c.total_pis, 0))}</div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, position: "relative", display: "flex" }}>
        
        {/* LEFT PANEL: Top Clusters */}
        <div style={{
          width: "320px",
          borderRight: "1px solid var(--border)",
          background: "var(--bg-secondary)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto"
        }}>
          <div style={{ padding: "16px", borderBottom: "1px solid var(--border)", fontSize: "12px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", textTransform: "uppercase" }}>
            Top Hotspots
          </div>
          
          <div style={{ display: "flex", flexDirection: "column" }}>
            {topClusters.map((c, i) => (
              <button 
                key={c.cluster_id}
                onClick={() => setSelectedClusterId(c.cluster_id)}
                aria-label={`Cluster ${c.cluster_id}: ${c.top_road}, ${c.mean_pis.toFixed(1)} PIS, ${formatNumber(c.n_violations)} violations`}
                aria-pressed={selectedClusterId === c.cluster_id}
                style={{
                  textAlign: "left",
                  padding: "16px",
                  borderBottom: "1px solid var(--border)",
                  background: selectedClusterId === c.cluster_id ? "rgba(59, 130, 246, 0.08)" : "transparent",
                  borderLeft: selectedClusterId === c.cluster_id ? "3px solid var(--accent)" : "3px solid transparent",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>Cluster #{c.cluster_id}</div>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--danger)" }}>{c.mean_pis.toFixed(1)} PIS</div>
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "4px" }}>
                  {c.top_road}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {formatNumber(c.n_violations)} violations
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* CENTER: Bubble Map */}
        <div style={{ flex: 1, position: "relative" }}>
          <ClusterBubbleMap 
            clusters={clusters} 
            selectedClusterId={selectedClusterId} 
            onClusterClick={setSelectedClusterId} 
          />
        </div>

        {/* RIGHT PANEL (Slide-over): Cluster Detail */}
        <ClusterPanel 
          clusterId={selectedClusterId} 
          open={selectedClusterId !== null} 
          onClose={() => setSelectedClusterId(null)} 
        />
      </div>
    </div>
  );
}
