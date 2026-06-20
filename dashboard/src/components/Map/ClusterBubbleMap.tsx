"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { type ClusterSummary } from "@/lib/api";

interface Props {
  clusters: ClusterSummary[];
  selectedClusterId: number | null;
  onClusterClick: (clusterId: number) => void;
}

// Color scale for mean PIS (Severity)
function getClusterColor(pis: number): string {
  if (pis > 60) return "#ef4444"; // Red (Critical)
  if (pis > 40) return "#f97316"; // Orange (High)
  if (pis > 20) return "#eab308"; // Yellow (Medium)
  return "#22c55e"; // Green (Low)
}

export default function ClusterBubbleMap({ clusters, selectedClusterId, onClusterClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const markersRef = useRef<Record<number, L.Circle>>({});

  // Initialize map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [12.9716, 77.5946],
      zoom: 12,
      zoomControl: false,
      preferCanvas: true,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { attribution: "&copy; CARTO", maxZoom: 19 }
    ).addTo(map);

    const layer = L.layerGroup().addTo(map);
    layerRef.current = layer;
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      markersRef.current = {};
    };
  }, []);

  // Render clusters
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    markersRef.current = {};

    if (!clusters || clusters.length === 0) return;

    const bounds: L.LatLngExpression[] = [];

    clusters.forEach((cluster) => {
      const color = getClusterColor(cluster.mean_pis);
      const isSelected = selectedClusterId === cluster.cluster_id;

      // Base radius on radius_m, but ensure a minimum visual size (e.g. 50m)
      const radius = Math.max(cluster.radius_m || 50, 50);

      const circle = L.circle([cluster.mean_lat, cluster.mean_lon], {
        color: color,
        fillColor: color,
        fillOpacity: isSelected ? 0.6 : 0.3,
        weight: isSelected ? 3 : 1,
        className: "cluster-bubble",
      })
        .bindTooltip(
          `<b>Cluster #${cluster.cluster_id}</b><br/>` +
          `Top Road: ${cluster.top_road}<br/>` +
          `Violations: ${cluster.n_violations}<br/>` +
          `Severity (PIS): ${cluster.mean_pis.toFixed(1)}`,
          { className: "prop-tooltip" } // Reuse same tooltip class
        )
        .on("click", () => {
          onClusterClick(cluster.cluster_id);
        })
        .addTo(layer);

      markersRef.current[cluster.cluster_id] = circle;
      bounds.push([cluster.mean_lat, cluster.mean_lon]);
    });

    // We only fitBounds if no cluster is selected, otherwise we let the selection logic handle map panning
    if (bounds.length > 0 && !selectedClusterId) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50], maxZoom: 13 });
    }
  }, [clusters, onClusterClick]); // Intentionally omitting selectedClusterId so we don't redraw everything on select

  // Update selected style
  useEffect(() => {
    if (!mapRef.current) return;
    const markers = markersRef.current;
    
    Object.entries(markers).forEach(([id, circle]) => {
      const isSelected = Number(id) === selectedClusterId;
      const color = circle.options.color;
      circle.setStyle({
        fillOpacity: isSelected ? 0.6 : 0.3,
        weight: isSelected ? 3 : 1,
        color: isSelected ? "#fff" : color, // Highlight border
      });
      if (isSelected) {
        circle.bringToFront();
        mapRef.current!.flyTo(circle.getLatLng(), 15, { duration: 0.5 });
      }
    });
  }, [selectedClusterId]);

  return (
    <>
      <style jsx global>{`
        .prop-tooltip {
          background: #0f172a !important;
          border: 1px solid #334155 !important;
          border-radius: 8px !important;
          color: #f1f5f9 !important;
          font-size: 12px !important;
          padding: 8px 12px !important;
          box-shadow: 0 4px 16px rgba(0,0,0,0.6) !important;
        }
        .prop-tooltip::before { border-top-color: #334155 !important; }
        .cluster-bubble {
          transition: all 0.2s ease;
          cursor: pointer;
        }
        .cluster-bubble:hover {
          fill-opacity: 0.8 !important;
        }
      `}</style>
      <div ref={containerRef} style={{ width: "100%", height: "100%", borderRadius: "var(--radius)", overflow: "hidden" }} />
    </>
  );
}
