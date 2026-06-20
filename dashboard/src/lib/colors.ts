/** Impact score → color mapping */
export function impactToColor(impact: number): string {
  if (impact >= 0.8) return "#dc2626";    // red-600
  if (impact >= 0.6) return "#ea580c";    // orange-600
  if (impact >= 0.4) return "#d97706";    // amber-600
  if (impact >= 0.2) return "#65a30d";    // lime-600
  return "#16a34a";                        // green-600
}

/** Risk band → color */
export function riskBandColor(band: string): string {
  switch (band) {
    case "critical": return "#dc2626";
    case "high": return "#ea580c";
    case "medium": return "#d97706";
    case "low": return "#16a34a";
    default: return "#6b7280";
  }
}

/** Tier → label */
export function tierLabel(tier: number): string {
  switch (tier) {
    case 1: return "Residential";
    case 2: return "Tertiary";
    case 3: return "Secondary";
    case 4: return "Primary";
    case 5: return "Trunk";
    case 6: return "Motorway";
    default: return "Link/Service";
  }
}

/** Format large numbers */
export function formatNumber(n: number): string {
  if (n >= 10_000_000) return `${(n / 10_000_000).toFixed(1)}Cr`;
  if (n >= 100_000) return `${(n / 100_000).toFixed(1)}L`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toFixed(0);
}

/** Impact score gradient for CSS */
export function impactGradient(impact: number): string {
  const pct = Math.min(impact * 100, 100);
  return `linear-gradient(90deg, ${impactToColor(impact)} ${pct}%, var(--bg-secondary) ${pct}%)`;
}
