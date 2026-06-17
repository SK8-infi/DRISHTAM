"""Wrapper to run Phase 1 pipeline with file-based logging.

Writes progress to pipeline_status.txt so we can check progress
even if the terminal connection drops.
"""

from __future__ import annotations

import datetime
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "pipeline_status.txt"


def log(msg: str) -> None:
    """Log a message to both stdout and the status file."""
    print(msg, flush=True)
    with STATUS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")


try:
    # Clear status file
    STATUS_FILE.write_text("Pipeline starting...\n", encoding="utf-8")

    log("Importing modules...")
    sys.path.insert(0, str(PROJECT_ROOT))

    from drishtam.config import setup_logging

    setup_logging()

    log("Step 1: Loading violations...")
    from drishtam.config import VIOLATION_PATH
    from drishtam.data_pipeline import load_violations

    viol_df = load_violations(VIOLATION_PATH)
    log(f"  Loaded {len(viol_df)} violations")

    log("Step 2: Loading road network (this takes ~20s)...")
    from drishtam.config import OSM_CACHE_PATH
    from drishtam.data_pipeline import load_road_network

    graph, nodes_gdf, edges_gdf = load_road_network(OSM_CACHE_PATH)
    log(f"  Loaded {len(edges_gdf)} edges, {len(nodes_gdf)} nodes")

    log("Step 3: Loading events...")
    from drishtam.config import EVENT_PATH
    from drishtam.data_pipeline import load_events

    events_df = load_events(EVENT_PATH)
    log(f"  Loaded {len(events_df)} events")

    log("Step 4: Enriching violations (heaviest step, 2-5 min)...")
    from drishtam.data_pipeline import enrich_violations

    enriched_df = enrich_violations(viol_df, edges_gdf, nodes_gdf)
    log(f"  Enriched: {enriched_df.shape}")

    log("Step 5: Running verification...")
    from drishtam.verification import print_enrichment_summary, verify_enriched_data

    checks = verify_enriched_data(enriched_df)
    log(f"  Verification: {sum(checks.values())}/{len(checks)} passed")
    summary = print_enrichment_summary(enriched_df)

    log("Step 6: Saving parquet...")
    from drishtam.config import DATA_DIR, ENRICHED_DATA_PATH

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    save_cols = [c for c in enriched_df.columns if c not in ["violation_type_raw", "nearest_edge_idx"]]
    save_df = enriched_df[save_cols].copy()
    if "violation_types_list" in save_df.columns:
        save_df["violation_types_list"] = save_df["violation_types_list"].apply(
            lambda x: "|".join(x) if isinstance(x, list) else str(x)
        )
    save_df.to_parquet(ENRICHED_DATA_PATH, index=False, engine="pyarrow")
    size_mb = ENRICHED_DATA_PATH.stat().st_size / 1e6
    log(f"  Saved: {ENRICHED_DATA_PATH} ({size_mb:.1f} MB)")

    log("Step 7: Generating visualizations...")
    import matplotlib

    matplotlib.use("Agg")

    from drishtam.config import RESEARCH_DIR

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # Import visualization functions properly via importlib
    import importlib.util

    viz_spec = importlib.util.spec_from_file_location(
        "build_enriched_data",
        PROJECT_ROOT / "scripts" / "01_build_enriched_data.py",
    )
    viz_module = importlib.util.module_from_spec(viz_spec)
    viz_spec.loader.exec_module(viz_module)

    viz_module.generate_enrichment_visualizations(enriched_df, RESEARCH_DIR)
    viz_module.save_research_report(enriched_df, summary, RESEARCH_DIR)
    log("  Visualizations and report saved")

    log("=" * 50)
    log("PHASE 1 COMPLETE!")
    log(f"Output: {ENRICHED_DATA_PATH}")
    log("=" * 50)

except Exception as e:
    log(f"ERROR: {e}")
    log(traceback.format_exc())
    sys.exit(1)
