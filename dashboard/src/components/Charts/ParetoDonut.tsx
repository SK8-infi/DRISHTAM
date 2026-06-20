"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const data = [
  { name: "Critical Violations (13.8%)", value: 80, fill: "var(--accent)" },
  { name: "Other Violations (86.2%)", value: 20, fill: "var(--bg-elevated)" }
];

export default function ParetoDonut() {
  return (
    <div style={{ width: "100%", height: 160, position: "relative" }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={70}
            stroke="none"
            dataKey="value"
            animationDuration={1500}
            animationEasing="ease-out"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip 
            contentStyle={{ background: "var(--bg-card)", borderColor: "var(--border)", borderRadius: "var(--radius-sm)" }}
            itemStyle={{ color: "var(--text-primary)" }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div style={{
        position: "absolute",
        top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        textAlign: "center"
      }}>
        <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)" }}>80%</div>
        <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Impact</div>
      </div>
    </div>
  );
}
