"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { type SegmentLight } from "@/lib/api";
import { impactToColor } from "@/lib/colors";

interface Props {
  mode: "impact" | "risk" | "patrol";
  segments: SegmentLight[];
  riskSegments?: any[];
  patrolAssignments?: any[];
  onSegmentClick?: (seg: SegmentLight) => void;
  onMapMove?: (bbox: { lat_min: number; lat_max: number; lon_min: number; lon_max: number }) => void;
}

export default function SegmentMap({ mode, segments, riskSegments = [], patrolAssignments = [], onSegmentClick, onMapMove }: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [12.9716, 77.5946],
      zoom: 12,
      zoomControl: true,
      preferCanvas: true, // Critical for performance with thousands of lines/markers
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        attribution: '&copy; CARTO',
        maxZoom: 19,
      }
    ).addTo(map);

    map.on("moveend", () => {
      const bounds = map.getBounds();
      if (onMapMove) {
        onMapMove({
          lat_min: bounds.getSouth(),
          lat_max: bounds.getNorth(),
          lon_min: bounds.getWest(),
          lon_max: bounds.getEast(),
        });
      }
    });

    const layerGroup = L.layerGroup().addTo(map);
    layerGroupRef.current = layerGroup;
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerGroupRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update render based on mode
  useEffect(() => {
    const map = mapRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    if (mode === "impact") {
      segments.forEach((seg) => {
        // If we have line geometry, draw a Polyline corridor
        if (seg.lat_u && seg.lon_u && seg.lat_v && seg.lon_v) {
          const color = impactToColor(seg.impact_gbm);
          const weight = seg.impact_gbm > 0.6 ? 4 : seg.impact_gbm > 0.4 ? 3 : 2;
          
          L.polyline([[seg.lat_u, seg.lon_u], [seg.lat_v, seg.lon_v]], {
            color,
            weight,
            opacity: 0.8,
            lineCap: "round",
            lineJoin: "round"
          })
            .bindTooltip(
              `<b>${seg.road_name || "Unnamed"}</b><br/>Impact: ${seg.impact_gbm.toFixed(3)}<br/>Tier: ${seg.tier} · ${seg.lanes}L`,
              { className: "segment-tooltip" }
            )
            .on("click", () => onSegmentClick && onSegmentClick(seg))
            .addTo(layerGroup);
        } else {
          // Fallback if no geometry
          L.circleMarker([seg.lat, seg.lon], {
            radius: 4,
            fillColor: impactToColor(seg.impact_gbm),
            fillOpacity: 0.8,
            color: impactToColor(seg.impact_gbm),
            weight: 1,
            opacity: 0.9,
          })
            .bindTooltip(
              `<b>${seg.road_name || "Unnamed"}</b><br/>Impact: ${seg.impact_gbm.toFixed(3)}`,
              { className: "segment-tooltip" }
            )
            .on("click", () => onSegmentClick && onSegmentClick(seg))
            .addTo(layerGroup);
        }
      });
    } else if (mode === "risk") {
      riskSegments.forEach((risk) => {
        // Normalize radius
        const scale = Math.min(2, Math.max(0.5, risk.risk_score * 0.05));
        
        const riskIcon = L.divIcon({
          className: "custom-div-icon",
          html: `<div class="risk-blob" style="transform: scale(${scale})"></div>`,
          iconSize: [60, 60],
          iconAnchor: [30, 30]
        });

        L.marker([risk.lat, risk.lon], { icon: riskIcon })
          .bindTooltip(
            `<b>${risk.road_name || "Unnamed"}</b><br/>Risk Score: ${risk.risk_score.toFixed(1)}`,
            { className: "segment-tooltip" }
          )
          .addTo(layerGroup);
      });
    } else if (mode === "patrol") {
      patrolAssignments.forEach((patrol) => {
        const patrolIcon = L.divIcon({
          className: "custom-div-icon",
          html: `
            <div class="patrol-target">
              <div class="patrol-dot"></div>
              <div class="patrol-ring"></div>
            </div>
          `,
          iconSize: [40, 40],
          iconAnchor: [20, 20]
        });

        L.marker([patrol.lat, patrol.lon], { icon: patrolIcon })
          .bindTooltip(
            `<b>Officer: ${patrol.officer_id}</b><br/>${patrol.road_name}<br/>Expected ROI: ${patrol.expected_roi}`,
            { className: "segment-tooltip" }
          )
          .addTo(layerGroup);
      });
    }
  }, [mode, segments, riskSegments, patrolAssignments, onSegmentClick]);

  return (
    <>
      <style jsx global>{`
        .segment-tooltip {
          background: #1a2236 !important;
          border: 1px solid #334155 !important;
          border-radius: 8px !important;
          color: #f1f5f9 !important;
          font-size: 12px !important;
          padding: 8px 12px !important;
          box-shadow: 0 4px 12px rgba(0,0,0,0.5) !important;
        }
        .segment-tooltip::before {
          border-top-color: #334155 !important;
        }
        .custom-div-icon {
          background: transparent;
          border: none;
        }
        .risk-blob {
          width: 100%;
          height: 100%;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(239, 68, 68, 0.9) 0%, rgba(239, 68, 68, 0.4) 40%, transparent 70%);
          animation: pulse-risk 2s ease-in-out infinite alternate;
          mix-blend-mode: screen;
        }
        @keyframes pulse-risk {
          0% { opacity: 0.6; transform: scale(0.8) translate(-50%, -50%); transform-origin: top left; }
          100% { opacity: 1; transform: scale(1.2) translate(-50%, -50%); transform-origin: top left; }
        }
        .patrol-target {
          position: relative;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .patrol-dot {
          width: 8px;
          height: 8px;
          background: #3b82f6;
          border-radius: 50%;
          box-shadow: 0 0 10px 2px rgba(59, 130, 246, 0.8);
          z-index: 2;
        }
        .patrol-ring {
          position: absolute;
          width: 24px;
          height: 24px;
          border: 1.5px solid rgba(59, 130, 246, 0.8);
          border-radius: 50%;
          animation: ping-ring 2s cubic-bezier(0, 0, 0.2, 1) infinite;
        }
        @keyframes ping-ring {
          75%, 100% {
            transform: scale(2.5);
            opacity: 0;
          }
        }
      `}</style>
      <div ref={containerRef} role="application" aria-label="Interactive map showing traffic enforcement segments" style={{ width: "100%", height: "100%", borderRadius: "var(--radius)", overflow: "hidden" }} />
    </>
  );
}
