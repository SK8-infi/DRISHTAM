"use client";

import { useEffect, useRef, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw";
import "leaflet-draw/dist/leaflet.draw.css";
import { type WhatIfResult } from "@/lib/api";

const HOP_STYLES: Record<number, { color: string; weight: number; opacity: number; label: string; glowColor: string }> = {
  0: { color: "#22c55e", weight: 5, opacity: 1, label: "Direct (Hop 0)", glowColor: "rgba(34, 197, 94, 0.6)" },
  1: { color: "#eab308", weight: 4, opacity: 0.85, label: "Neighbor (Hop 1)", glowColor: "rgba(234, 179, 8, 0.5)" },
  2: { color: "#f97316", weight: 3, opacity: 0.7, label: "Ripple (Hop 2)", glowColor: "rgba(249, 115, 22, 0.4)" },
};

interface Props {
  result: WhatIfResult | null;
  onAreaSelected?: (bounds: { lat_min: number; lat_max: number; lon_min: number; lon_max: number }, polygon: [number, number][]) => void;
}

export default function PropagationMap({ result, onAreaSelected }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const drawnRef = useRef<L.FeatureGroup | null>(null);
  const drawControlRef = useRef<L.Control.Draw | null>(null);

  const onAreaSelectedRef = useRef(onAreaSelected);
  onAreaSelectedRef.current = onAreaSelected;

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

    const resultLayer = L.layerGroup().addTo(map);
    layerRef.current = resultLayer;

    // Drawing layer
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnRef.current = drawnItems;

    // Drawing controls
    const drawControl = new L.Control.Draw({
      position: "topright",
      draw: {
        polygon: {
          allowIntersection: false,
          shapeOptions: {
            color: "#8b5cf6",
            weight: 2,
            fillColor: "#8b5cf6",
            fillOpacity: 0.1,
          },
        },
        rectangle: {
          shapeOptions: {
            color: "#8b5cf6",
            weight: 2,
            fillColor: "#8b5cf6",
            fillOpacity: 0.1,
          },
        },
        circle: false,
        circlemarker: false,
        marker: false,
        polyline: false,
      },
    });
    map.addControl(drawControl);
    drawControlRef.current = drawControl;

    // Handle draw events — use LeafletEvent + assertion since @types/leaflet-draw
    // doesn't perfectly align with leaflet's event handler signature
    map.on(L.Draw.Event.CREATED, (e: L.LeafletEvent) => {
      drawnItems.clearLayers();
      const layer = (e as L.DrawEvents.Created).layer as L.Polygon;
      drawnItems.addLayer(layer);

      // Extract bounds and polygon vertices
      const bounds = layer.getBounds();
      const bbox = {
        lat_min: bounds.getSouth(),
        lat_max: bounds.getNorth(),
        lon_min: bounds.getWest(),
        lon_max: bounds.getEast(),
      };

      let polygon: [number, number][] = [];
      if ('getLatLngs' in layer) {
        const latlngs = layer.getLatLngs();
        // Polygons return nested arrays
        const points = Array.isArray(latlngs[0]) ? latlngs[0] : latlngs;
        polygon = (points as L.LatLng[]).map((ll: L.LatLng) => [ll.lat, ll.lng] as [number, number]);
      }

      if (onAreaSelectedRef.current) {
        onAreaSelectedRef.current(bbox, polygon);
      }
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      drawnRef.current = null;
    };
  }, []);

  // Render propagation when result changes
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    if (!result || result.propagation.length === 0) return;

    const allBounds: L.LatLngExpression[] = [];
    const enforcedNames = new Set(result.road_names.map(r => r.toLowerCase()));

    const renderSegment = (
      seg: { lat: number; lon: number; lat_u: number; lon_u: number; lat_v: number; lon_v: number; road_name: string; improvement: number },
      hop: number,
      style: typeof HOP_STYLES[0],
      isEnforced: boolean,
    ) => {
      const color = isEnforced ? "#06b6d4" : style.color;
      const glowColor = isEnforced ? "rgba(6, 182, 212, 0.6)" : style.glowColor;
      const weight = isEnforced ? 6 : style.weight;
      const hasGeometry = seg.lat_u && seg.lon_u && seg.lat_v && seg.lon_v &&
        (Math.abs(seg.lat_u - seg.lat_v) > 0.00001 || Math.abs(seg.lon_u - seg.lon_v) > 0.00001);

      if (hasGeometry) {
        L.polyline([[seg.lat_u, seg.lon_u], [seg.lat_v, seg.lon_v]], {
          color: glowColor,
          weight: weight + 8,
          opacity: 0.4,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(layer);

        L.polyline([[seg.lat_u, seg.lon_u], [seg.lat_v, seg.lon_v]], {
          color,
          weight,
          opacity: style.opacity,
          lineCap: "round",
          lineJoin: "round",
        })
          .bindTooltip(
            `<b>${isEnforced ? "🛡️ ENFORCED: " : ""}${seg.road_name}</b><br/>` +
            `${isEnforced ? "" : `Hop ${hop} · `}Δ: -${seg.improvement.toFixed(3)}`,
            { className: "prop-tooltip" }
          )
          .addTo(layer);

        allBounds.push([seg.lat_u, seg.lon_u], [seg.lat_v, seg.lon_v]);
      }

      const dotIcon = L.divIcon({
        className: "prop-div-icon",
        html: `<div class="prop-dot" style="
          background: ${color};
          box-shadow: 0 0 ${isEnforced ? 16 : 10}px ${isEnforced ? 6 : 3}px ${glowColor};
          width: ${isEnforced ? 10 : hop === 0 ? 8 : 6}px;
          height: ${isEnforced ? 10 : hop === 0 ? 8 : 6}px;
        "></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      L.marker([seg.lat, seg.lon], { icon: dotIcon })
        .bindTooltip(
          `<b>${isEnforced ? "🛡️ ENFORCED: " : ""}${seg.road_name}</b><br/>` +
          `${isEnforced ? "" : `Hop ${hop} · `}Δ: -${seg.improvement.toFixed(3)}`,
          { className: "prop-tooltip" }
        )
        .addTo(layer);

      allBounds.push([seg.lat, seg.lon]);
    };

    // Collect all seg_idx already rendered in rings to avoid duplicates
    const renderedSegIds = new Set<number>();

    // FIRST: Render enforced roads as a dim cyan underlay from top_improved
    const enforcedSegs = result.top_improved.filter(seg =>
      enforcedNames.has(seg.road_name.toLowerCase())
    );
    for (const seg of enforcedSegs) {
      renderSegment(seg, -1, {
        color: "#06b6d4", weight: 3, opacity: 0.6, label: "Enforced",
        glowColor: "rgba(6, 182, 212, 0.3)"
      }, true);
      renderedSegIds.add(seg.seg_idx);
    }

    // SECOND: Render propagation rings ON TOP with their proper hop colors
    // Draw in reverse order (hop 2 first) so hop 0 is visually on top
    const sortedRings = [...result.propagation].sort((a, b) => b.hop - a.hop);

    for (const ring of sortedRings) {
      const style = HOP_STYLES[ring.hop] || HOP_STYLES[2];
      for (const seg of ring.items) {
        // Always use the hop color — never override to cyan
        renderSegment(seg, ring.hop, style, false);
        renderedSegIds.add(seg.seg_idx);
      }
    }

    if (allBounds.length > 0) {
      map.fitBounds(L.latLngBounds(allBounds), { padding: [50, 50], maxZoom: 14 });
    }
  }, [result]);

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
        .prop-div-icon { background: transparent !important; border: none !important; }
        .prop-dot {
          border-radius: 50%;
          position: absolute;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
        }
        /* Style leaflet-draw controls to match the dark theme */
        .leaflet-draw-toolbar a {
          background-color: rgba(10, 10, 10, 0.85) !important;
          border-color: #334155 !important;
          color: #e2e8f0 !important;
        }
        .leaflet-draw-toolbar a:hover {
          background-color: rgba(139, 92, 246, 0.3) !important;
          border-color: #8b5cf6 !important;
        }
        .leaflet-draw-actions a {
          background-color: rgba(10, 10, 10, 0.9) !important;
          color: #e2e8f0 !important;
          border-color: #334155 !important;
        }
        .leaflet-draw-actions a:hover {
          background-color: rgba(139, 92, 246, 0.3) !important;
        }
      `}</style>
      <div ref={containerRef} role="application" aria-label="Interactive What-If simulation map showing enforcement propagation" style={{ width: "100%", height: "100%", borderRadius: "var(--radius)", overflow: "hidden" }} />

      {/* Empty state overlay */}
      {!result && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.3)",
          borderRadius: "var(--radius)",
          pointerEvents: "none",
        }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ marginBottom: "12px", opacity: 0.5, color: "var(--text-muted)" }}>
              <svg aria-hidden="true" focusable="false" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/><line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/></svg>
            </div>
            <div style={{ fontSize: "14px", color: "var(--text-muted)", fontWeight: 500 }}>
              Select roads, use scenario cards,<br/>or <span style={{ color: "#a78bfa" }}>draw a shape</span> on the map
            </div>
          </div>
        </div>
      )}

      {/* Legend overlay */}
      {result && (
        <div style={{
          position: "absolute", bottom: 16, left: 16,
          background: "rgba(10, 10, 10, 0.85)",
          backdropFilter: "blur(12px)",
          border: "1px solid var(--border)",
          borderRadius: "8px",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          zIndex: 5,
        }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.5px", marginBottom: "2px" }}>
            PROPAGATION LEGEND
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11px", color: "#06b6d4" }}>
            <div style={{ width: 20, height: 4, background: "#06b6d4", borderRadius: 2, boxShadow: "0 0 6px rgba(6, 182, 212, 0.6)" }} />
            Enforced Roads
          </div>
          {Object.entries(HOP_STYLES).map(([hop, s]) => (
            <div key={hop} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11px", color: s.color }}>
              <div style={{ width: 20, height: s.weight, background: s.color, borderRadius: 2, boxShadow: `0 0 6px ${s.glowColor}` }} />
              {s.label}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
