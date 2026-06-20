"use client";

import { useEffect, useState, useRef } from "react";

interface Props {
  percentage: number; // e.g. 0.164 means 0.164%
  label?: string;
}

export default function ReductionGauge({ percentage, label = "Impact Reduction" }: Props) {
  const [animated, setAnimated] = useState(0);
  const rafRef = useRef<number>(0);

  // Normalize: the percentage is usually small (0.001 to ~5).
  // We'll display it as-is but scale the arc fill to max out at ~5%
  const maxDisplay = Math.max(5, percentage * 1.5);
  const fillFraction = Math.min(percentage / maxDisplay, 1);

  useEffect(() => {
    let start: number | null = null;
    const duration = 1800;

    const animate = (ts: number) => {
      if (!start) start = ts;
      const elapsed = ts - start;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimated(eased * percentage);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [percentage]);

  const size = 200;
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const animatedFill = (animated / Math.max(maxDisplay, 0.001));
  const offset = circumference * (1 - Math.min(animatedFill, 1));

  // Color gradient: red → amber → green based on percentage
  const getColor = (pct: number) => {
    if (pct >= 2) return "#22c55e";
    if (pct >= 1) return "#84cc16";
    if (pct >= 0.5) return "#eab308";
    if (pct >= 0.1) return "#f59e0b";
    return "#ef4444";
  };

  const color = getColor(animated);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        {/* Background track */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={strokeWidth}
        />
        {/* Animated arc */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke 0.3s ease", filter: `drop-shadow(0 0 8px ${color}80)` }}
        />
      </svg>
      {/* Center text overlay */}
      <div style={{
        position: "absolute",
        top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        textAlign: "center",
      }}>
        <div style={{
          fontSize: "36px",
          fontWeight: 800,
          fontFamily: "var(--font-mono)",
          color,
          lineHeight: 1,
        }}>
          -{animated.toFixed(3)}%
        </div>
        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", fontWeight: 500 }}>
          {label}
        </div>
      </div>
    </div>
  );
}
