"use client";

import { BarChart, Bar, ResponsiveContainer, Cell } from "recharts";

interface Props {
  dataArray: number[];
  color?: string;
}

export default function Sparkline({ dataArray, color = "var(--accent)" }: Props) {
  const chartData = dataArray.map((val, i) => ({ index: i, value: val }));

  return (
    <div style={{ width: "100%", height: "40px" }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <Bar dataKey="value" radius={[2, 2, 0, 0]} animationDuration={1000}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={color} opacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
