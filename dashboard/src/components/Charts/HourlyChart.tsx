"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface Props {
  data: Record<number, number>;
  gapHours: number[];
}

export default function HourlyChart({ data, gapHours }: Props) {
  const chartData = Array.from({ length: 24 }, (_, h) => ({
    hour: `${h.toString().padStart(2, "0")}:00`,
    violations: data[h] || 0,
    isGap: gapHours.includes(h),
  }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
        <XAxis
          dataKey="hour"
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={{ stroke: "#1e293b" }}
          tickLine={false}
          interval={2}
        />
        <YAxis
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: "rgba(255, 255, 255, 0.05)" }}
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
            color: "var(--text-primary)",
          }}
          itemStyle={{ color: "var(--text-primary)" }}
        />
        <Bar dataKey="violations" radius={[3, 3, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.isGap ? "#ef4444" : "#3b82f6"}
              fillOpacity={entry.isGap ? 0.8 : 0.6}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
