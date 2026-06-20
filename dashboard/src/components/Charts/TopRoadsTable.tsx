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
    <div className="table-container" style={{ maxHeight: 280, overflowY: "auto" }} role="region" aria-label="Top roads by congestion impact" tabIndex={0}>
      <table>
        <caption className="sr-only">Top 10 roads ranked by parking impact score (PIS)</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Road Name</th>
            <th scope="col">Total PIS</th>
            <th scope="col">Impact</th>
          </tr>
        </thead>
        <tbody>
          {roads.map((road, i) => (
            <tr key={i} className="interactive-row">
              <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{i + 1}</td>
              <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                <Link href={`/map?road=${encodeURIComponent(road.name)}`} style={{ color: "inherit", textDecoration: "none", display: "block" }} aria-label={`View ${road.name} on impact map`}>
                  {road.name}
                </Link>
              </td>
              <td style={{ fontFamily: "var(--font-mono)" }}>{formatNumber(road.total_pis)}</td>
              <td style={{ width: 120 }}>
                <div className="impact-bar" role="meter" aria-label={`Impact level for ${road.name}`} aria-valuenow={Math.round((road.total_pis / maxPis) * 100)} aria-valuemin={0} aria-valuemax={100}>
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
