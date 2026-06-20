"use client";

import { useEffect, useState } from "react";

interface Props {
  targetValue: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
}

export default function AnimatedCounter({ targetValue, duration = 1500, prefix = "", suffix = "" }: Props) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTimestamp: number | null = null;
    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      
      // easeOutCubic
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      
      setCount(easeProgress * targetValue);
      
      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };
    window.requestAnimationFrame(step);
  }, [targetValue, duration]);

  return (
    <span>
      {prefix}
      {count.toFixed(1)}
      {suffix}
    </span>
  );
}
