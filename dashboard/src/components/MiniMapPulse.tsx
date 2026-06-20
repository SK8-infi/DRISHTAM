"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";

const MapContainer = dynamic(() => import("react-leaflet").then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then((m) => m.TileLayer), { ssr: false });

export default function MiniMapPulse() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return <div style={{ height: 140, background: "#080808", borderRadius: "var(--radius)" }} />;

  return (
    <div className="mini-map-container" style={{
      position: "relative",
      width: "100%",
      height: "140px",
      borderRadius: "var(--radius)",
      overflow: "hidden",
      background: "#080808",
      border: "1px solid var(--border)"
    }}>
      <MapContainer 
        center={[12.9716, 77.5946]} 
        zoom={12} 
        zoomControl={false} 
        dragging={false} 
        scrollWheelZoom={false}
        doubleClickZoom={false}
        attributionControl={false}
        style={{ height: "100%", width: "100%", zIndex: 0 }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
      </MapContainer>

      {/* Pulsing City Center */}
      <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 10, pointerEvents: "none" }}>
        <div className="pulse-ring" style={{
          position: "absolute",
          top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          width: "80px", height: "80px",
          borderRadius: "50%",
          background: "var(--accent)",
          opacity: 0,
          animation: "pulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite"
        }} />
        <div style={{
          width: "12px", height: "12px",
          background: "var(--accent)",
          borderRadius: "50%",
          boxShadow: "0 0 16px 6px var(--accent-glow)",
          position: "relative",
          zIndex: 2
        }} />
      </div>

      <style jsx>{`
        @keyframes pulse {
          0% { transform: translate(-50%, -50%) scale(0.2); opacity: 0.8; }
          100% { transform: translate(-50%, -50%) scale(4); opacity: 0; }
        }
      `}</style>
      
      <div style={{
        position: "absolute",
        bottom: "8px", right: "8px",
        fontSize: "10px",
        fontFamily: "var(--font-mono)",
        color: "var(--accent-hover)",
        letterSpacing: "1px",
        display: "flex",
        alignItems: "center",
        gap: "6px",
        zIndex: 10,
        background: "rgba(0,0,0,0.6)",
        padding: "4px 8px",
        borderRadius: "4px",
        border: "1px solid var(--border-light)"
      }}>
        <div style={{width: 4, height: 4, borderRadius: 2, background: "var(--accent)"}} />
        LIVE CITY PULSE
      </div>
    </div>
  );
}
