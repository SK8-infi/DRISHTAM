import { Step } from "react-joyride";

/*
 * TUTORIAL STEPS — Comprehensive & Bug-Free
 * 
 * RULES for selectors:
 * 1. ALWAYS prefix with `.main-content` to scope inside the page content (avoids matching sidebar)
 * 2. NEVER use `body` or `main` as a target (centering bugs)
 * 3. NEVER use `placement: "center"` (Floating UI miscalculation)
 * 4. Only target VISIBLE, ALWAYS-MOUNTED elements
 * 5. For map pages, avoid targeting .leaflet-container directly (z-index issues)
 */

export const tutorialSteps: Record<string, Step[]> = {

  /* ═══════════════════════════════════════════════════════════
   *  OVERVIEW PAGE  (/)
   * ═══════════════════════════════════════════════════════════ */
  "/": [
    {
      target: ".main-content .page-header",
      content: "Welcome to DRISHTAM! This is the Dashboard Overview — your real-time command center powered by 3 machine learning engines. Let's walk through everything on this page.",
      title: "Dashboard Overview",
      skipBeacon: true,
    },
    {
      target: ".main-content .page-header + div",
      content: "This hero section shows the live Estimated Congestion Cost — the total financial impact of current traffic gridlock across Bengaluru, computed in real-time by our AI.",
      title: "Congestion Cost (Live)",
      skipBeacon: true,
    },
    {
      target: ".main-content .kpi-card:first-of-type",
      content: "The Pareto Donut reveals how impact is concentrated. A tiny fraction of violations cause the vast majority of network delays — the classic 80/20 rule, but skewed even further.",
      title: "Impact Concentration",
      skipBeacon: true,
    },
    {
      target: ".main-content .charts-grid",
      content: "The Hourly Distribution chart shows exactly when violations peak throughout the day. Red-highlighted bars indicate the enforcement gap — times when patrols are absent but violations spike.",
      title: "Hourly Violation Pattern",
      skipBeacon: true,
    },
  ],

  /* ═══════════════════════════════════════════════════════════
   *  MAP PAGE  (/map)
   *  Note: Don't target .leaflet-container (z-index issues).
   *  Start with the lens panel header which floats above the map.
   * ═══════════════════════════════════════════════════════════ */
  "/map": [
    {
      target: "#map-lens-panel",
      content: "Welcome to the Interactive Map! This is your geographic command center. Use the Map Lenses panel to switch between three AI-powered analytical overlays.",
      title: "Map Lenses Panel",
      skipBeacon: true,
    },
    {
      target: "#lens-impact",
      content: "IMPACT CORRIDORS (default): Visualizes the road network and color-codes each segment by its GBM-predicted congestion severity — from green (low impact) to red (critical). Click any segment for detailed stats.",
      title: "Lens 1: Impact Corridors",
      skipBeacon: true,
    },
    {
      target: "#lens-patrol",
      content: "OPTIMAL PATROL: Runs our optimization engine and shows exactly where officers should be deployed. When active, a timeline slider appears at the bottom and a patrol configuration panel on the right.",
      title: "Lens 2: Optimal Patrol",
      skipBeacon: true,
    },
    {
      target: "#lens-risk",
      content: "RISK FORECAST: The predictive engine. Maps out areas where our deep learning model predicts gridlock will emerge in upcoming hours, enabling preemptive deployment of patrol units.",
      title: "Lens 3: Risk Forecast",
      skipBeacon: true,
    },
    {
      target: "#impact-severity-legend",
      content: "Click on any severity level to filter the map and show only roads within that impact range. Click it again to reset the filter back to all roads.",
      title: "Impact Severity Filter",
      skipBeacon: true,
    },
  ],

  /* ═══════════════════════════════════════════════════════════
   *  STATIONS PAGE  (/stations)
   * ═══════════════════════════════════════════════════════════ */
  "/stations": [
    {
      target: ".main-content h2",
      content: "Welcome to the Station Explorer! This page lets you drill into every traffic police station's jurisdiction, compare performance, and identify underperforming areas.",
      title: "Station Explorer",
      skipBeacon: true,
    },
    {
      target: ".main-content button:first-of-type",
      content: "Use these division filter pills to narrow the station list by geographic area — East, West, North, or South. Select 'All' to see every station in the city.",
      title: "Division Filters",
      skipBeacon: true,
    },
    {
      target: ".main-content .card:first-of-type",
      content: "Each station card shows its name, division, total violations, mean risk score (PIS), and road count. Click any card to select that station and see its jurisdiction highlighted on the map.",
      title: "Station Cards",
      skipBeacon: true,
    },
  ],

  /* ═══════════════════════════════════════════════════════════
   *  CLUSTERS PAGE  (/clusters)
   * ═══════════════════════════════════════════════════════════ */
  "/clusters": [
    {
      target: ".main-content h2",
      content: "Welcome to the Cluster Explorer! This page uses HDBSCAN machine learning to automatically group geographically close violations into macro-level hotspot clusters.",
      title: "Cluster Explorer",
      skipBeacon: true,
    },
    {
      target: ".main-content button:first-of-type",
      content: "The left sidebar ranks the top hotspot clusters by severity. Each shows the cluster ID, primary road, mean PIS (risk score), and violation count. Click any to inspect it on the map.",
      title: "Top Hotspots Panel",
      skipBeacon: true,
    },
  ],

  /* ═══════════════════════════════════════════════════════════
   *  WHAT-IF SIMULATOR  (/whatif)
   * ═══════════════════════════════════════════════════════════ */
  "/whatif": [
    {
      target: ".main-content h2",
      content: "Welcome to the What-If Simulator! This is the most powerful tool in DRISHTAM. Select roads or stations, run the AI engine, and instantly see how enforcement would reduce congestion.",
      title: "What-If Simulator",
      skipBeacon: true,
    },
    {
      target: ".main-content button:first-of-type",
      content: "Start with Quick Scenarios — pre-configured enforcement plans like 'Top 5 Roads', 'Evening Peak', 'ORR Corridor', or 'CBD Core'. Click any to instantly load and run the simulation.",
      title: "Quick Scenarios",
      skipBeacon: true,
    },
    {
      target: ".main-content select",
      content: "You can also constrain the simulation to a specific police station's jurisdiction. Select a station here, and only roads within that station's area will be analyzed.",
      title: "Station Constraint",
      skipBeacon: true,
    },
    {
      target: ".main-content input[type='text']",
      content: "Or build a fully custom simulation by searching and selecting individual roads. Check roads from the list below, then click 'Run Simulation' at the bottom.",
      title: "Custom Road Selection",
      skipBeacon: true,
    },
  ],

  /* ═══════════════════════════════════════════════════════════
   *  INSIGHTS PAGE  (/insights)
   * ═══════════════════════════════════════════════════════════ */
  "/insights": [
    {
      target: ".main-content .page-header",
      content: "Welcome to Executive Insights! This page automatically analyzes all data from the enforcement engines to surface data-driven discoveries, anomalies, and actionable recommendations.",
      title: "Executive Insights",
      skipBeacon: true,
    },
    {
      target: ".main-content .card.animate-in:first-of-type",
      content: "Each Evidence Card shows a key finding with its category, severity, hero metric, and detailed explanation. Cards with a 'See Evidence' link let you jump directly to the relevant dashboard page.",
      title: "Evidence Cards",
      skipBeacon: true,
    },
    {
      target: ".main-content .card:has(table)",
      content: "The ML Experiment Log shows every model architecture tested during development, ranked by score. The champion model is the one currently powering the live system.",
      title: "ML Experiment Log",
      skipBeacon: true,
    },
  ],
};
