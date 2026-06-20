"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { StationSummary } from "@/lib/api";
import { Delaunay } from "d3-delaunay";

interface Props {
  stations: StationSummary[];
  selectedStation: string | null;
  onStationClick: (stationName: string) => void;
}

export default function StationBoundaryMap({ stations, selectedStation, onStationClick }: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapRef.current = L.map(containerRef.current, {
      center: [12.97, 77.59],
      zoom: 11,
      zoomControl: false,
      attributionControl: false,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png").addTo(mapRef.current);
    L.control.zoom({ position: "bottomright" }).addTo(mapRef.current);

    layerGroupRef.current = L.layerGroup().addTo(mapRef.current);
  }, []);

  useEffect(() => {
    if (!mapRef.current || !layerGroupRef.current || stations.length === 0) return;

    layerGroupRef.current.clearLayers();

    // 1. Calculate Voronoi Polygons
    // The Delaunay points must be array of [x, y] -> [lon, lat] is standard for math
    const points = stations.map(s => [s.lon, s.lat] as [number, number]);
    
    // Bounds: minLon, minLat, maxLon, maxLat
    const minLon = Math.min(...points.map(p => p[0])) - 0.05;
    const minLat = Math.min(...points.map(p => p[1])) - 0.05;
    const maxLon = Math.max(...points.map(p => p[0])) + 0.05;
    const maxLat = Math.max(...points.map(p => p[1])) + 0.05;
    
    const delaunay = Delaunay.from(points);
    const voronoi = delaunay.voronoi([minLon, minLat, maxLon, maxLat]);

    stations.forEach((stn, i) => {
      let color = "#9ca3af";
      if (stn.division === "East") color = "#3b82f6";
      if (stn.division === "West") color = "#f97316";
      if (stn.division === "North") color = "#22c55e";
      if (stn.division === "South") color = "#a855f7";

      const isSelected = selectedStation === stn.station_name;

      // Draw Polygon
      const polygonPoints = voronoi.cellPolygon(i);
      if (polygonPoints) {
        // convert [lon, lat] back to [lat, lon] for Leaflet
        const latlngs = Array.from(polygonPoints).map((p: [number, number]) => [p[1], p[0]] as [number, number]);
        
        const poly = L.polygon(latlngs, {
          color: color,
          weight: isSelected ? 3 : 1,
          opacity: isSelected ? 1 : 0.4,
          fillColor: color,
          fillOpacity: isSelected ? 0.25 : 0.1,
          className: "voronoi-poly",
        });

        poly.on("click", () => onStationClick(stn.station_name));
        poly.on("mouseover", () => {
          if (!isSelected) {
            poly.setStyle({ fillOpacity: 0.35, weight: 2 });
          }
        });
        poly.on("mouseout", () => {
          if (!isSelected) {
            poly.setStyle({ fillOpacity: 0.1, weight: 1 });
          }
        });
        poly.bindTooltip(`<b>${stn.station_name}</b><br/>${stn.division} Division`, { className: "station-tooltip" });
        poly.addTo(layerGroupRef.current!);
      }

      // Draw Centroid Marker
      const radius = Math.min(25, Math.max(6, Math.sqrt(stn.violations) * 0.1));
      L.circleMarker([stn.lat, stn.lon], {
        radius: radius,
        fillColor: color,
        fillOpacity: 0.8,
        color: "#fff",
        weight: 1,
        opacity: 0.8,
      })
        .on("click", () => onStationClick(stn.station_name))
        .addTo(layerGroupRef.current!);
    });

  }, [stations, selectedStation, onStationClick]);

  return (
    <>
      <style jsx global>{`
        .station-tooltip {
          background: rgba(10, 10, 10, 0.9) !important;
          border: 1px solid #334155 !important;
          border-radius: 8px !important;
          color: #f1f5f9 !important;
          font-size: 12px !important;
          padding: 8px 12px !important;
          backdrop-filter: blur(4px);
        }
      `}</style>
      <div ref={containerRef} role="application" aria-label="Interactive map showing police station jurisdiction boundaries" style={{ width: "100%", height: "100%", background: "#0a0a0a" }} />
    </>
  );
}
