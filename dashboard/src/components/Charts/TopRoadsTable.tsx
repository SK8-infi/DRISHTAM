"use client";

import { TopRoad } from "@/lib/api";
import { formatNumber } from "@/lib/colors";
import Link from "next/link";

interface Props {
  roads: TopRoad[];
}

export default function TopRoadsTable({ roads }: Props) {
  const maxPis = Math.max(...roads.map(r => r.total_pis), 1);

  return (
    <div className="table-container" style={{ maxHeight: 280, overflowY: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Road Name</th>
            <th>Total PIS</th>
            <th>Impact</th>
          </tr>
        </thead>
        <tbody>
          {roads.map((road, i) => (
            <tr key={i} className="interactive-row" title="Click to view detailed impact map">
              <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{i + 1}</td>
              <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                <Link href={`/map?road=${encodeURIComponent(road.name)}`} style={{ color: "inherit", textDecoration: "none", display: "block" }}>
                  {road.name}
                </Link>
              </td>
              <td style={{ fontFamily: "var(--font-mono)" }}>{formatNumber(road.total_pis)}</td>
              <td style={{ width: 120 }}>
                <div className="impact-bar">
                  <div
                    className="impact-bar-fill"
                    style={{
                      width: `${(road.total_pis / maxPis) * 100}%`,
                      background: `linear-gradient(90deg, #3b82f6, #ef4444)`,
                    }}
                  />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <style jsx>{`
        .interactive-row {
          cursor: pointer;
          transition: all var(--transition);
        }
        .interactive-row:hover {
          background: rgba(59, 130, 246, 0.1) !important;
        }
        .interactive-row:hover td {
          color: var(--accent) !important;
        }
      `}</style>
    </div>
  );
}
