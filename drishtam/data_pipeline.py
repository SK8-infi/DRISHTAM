"""DRISHTAM data pipeline — loading, cleaning, and spatial enrichment.

This module handles the entire data flow from raw CSVs + OSM GraphML
to the enriched violations parquet file. Every violation gets mapped to
its nearest road segment and annotated with 40+ engineered features.

Key functions:
    load_violations: Load and clean violation CSV
    load_road_network: Load OSM GraphML → nodes/edges GeoDataFrames
    load_events: Load ASTraM event CSV
    enrich_violations: Full pipeline — spatial + temporal + density enrichment
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd
    import networkx as nx

from drishtam.config import (
    BBOX,
    BUS_STOP_RADIUS_M,
    DEFAULT_ROAD_INFO,
    DEFAULT_VEHICLE_WIDTH_M,
    DEFAULT_VIOLATION_SEVERITY,
    IST_OFFSET_HOURS,
    IST_OFFSET_MINUTES,
    LAT_TO_METERS,
    LON_TO_METERS,
    METRO_STATION_RADIUS_M,
    NEIGHBORHOOD_RADIUS_500M,
    NEIGHBORHOOD_RADIUS_M,
    ROAD_HIERARCHY,
    TEMPORAL_FACTORS,
    VEHICLE_WIDTH_M,
    VIOLATION_SEVERITY,
    WEEKEND_MULTIPLIER,
)
from drishtam.exceptions import DataValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# 1. DATA LOADERS
# =============================================================================


def load_violations(path: Path) -> pd.DataFrame:
    """Load and clean the violation dataset.

    Parses dates, filters to Bengaluru bbox, extracts violation types,
    maps vehicle widths, and creates IST temporal features.

    Args:
        path: Path to the raw violation CSV file.

    Returns:
        Cleaned DataFrame with ~298K records and base features.

    Raises:
        FileNotFoundError: If the CSV file doesn't exist.
        DataValidationError: If record count is wildly off.
    """
    path = Path(path)
    if not path.exists():
        msg = f"Violation CSV not found: {path}"
        raise FileNotFoundError(msg)

    logger.info("Loading violations from %s", path.name)
    start = time.perf_counter()

    df = pd.read_csv(
        path,
        dtype={"id": str, "vehicle_number": str, "vehicle_type": str},
        low_memory=False,
    )
    logger.info("Raw records: %d", len(df))

    # Parse datetime explicitly (parse_dates kwarg can't handle tz-aware strings reliably)
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True)

    # Drop rows with NaT datetime
    nat_count = df["created_datetime"].isna().sum()
    if nat_count > 0:
        logger.warning("Dropping %d rows with NaT datetime", nat_count)
        df = df.dropna(subset=["created_datetime"])

    # Filter to Bengaluru bounding box
    bbox_mask = (
        (df["latitude"] >= BBOX["lat_min"])
        & (df["latitude"] <= BBOX["lat_max"])
        & (df["longitude"] >= BBOX["lon_min"])
        & (df["longitude"] <= BBOX["lon_max"])
    )
    n_outside = (~bbox_mask).sum()
    if n_outside > 0:
        logger.info("Filtering %d records outside Bengaluru bbox", n_outside)
    df = df[bbox_mask].copy()

    # --- Violation type parsing ---
    df["violation_type_raw"] = df["violation_type"]
    df["violation_types_list"] = df["violation_type"].apply(_parse_violation_types)
    df["primary_violation"] = df["violation_types_list"].apply(lambda vt: vt[0] if len(vt) > 0 else "UNKNOWN")
    df["violation_count"] = df["violation_types_list"].apply(len)
    df["is_congestion_relevant"] = df["violation_types_list"].apply(lambda vt: any(v in VIOLATION_SEVERITY for v in vt))

    # --- Violation severity (max across all tagged types) ---
    df["violation_severity"] = df["violation_types_list"].apply(
        lambda vt: max(
            (VIOLATION_SEVERITY.get(v, DEFAULT_VIOLATION_SEVERITY) for v in vt), default=DEFAULT_VIOLATION_SEVERITY
        )
    )

    # --- Vehicle width mapping ---
    df["vehicle_type_clean"] = df["vehicle_type"].str.strip().str.upper()
    df["vehicle_width_m"] = df["vehicle_type_clean"].map(VEHICLE_WIDTH_M).fillna(DEFAULT_VEHICLE_WIDTH_M)

    # --- IST datetime ---
    df["created_datetime_ist"] = df["created_datetime"] + pd.Timedelta(
        hours=IST_OFFSET_HOURS, minutes=IST_OFFSET_MINUTES
    )

    # --- Temporal features ---
    df["hour_ist"] = df["created_datetime_ist"].dt.hour
    df["day_of_week"] = df["created_datetime_ist"].dt.dayofweek  # 0=Mon, 6=Sun
    df["month"] = df["created_datetime_ist"].dt.month
    df["is_weekend"] = df["day_of_week"].isin([5, 6])
    df["is_peak_morning"] = df["hour_ist"].between(8, 9)  # 8:00-9:59
    df["is_peak_evening"] = df["hour_ist"].between(17, 19)  # 17:00-19:59

    # Cyclical encoding (for ML models)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_ist"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_ist"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    # Temporal factor from config lookup
    df["temporal_factor"] = df["hour_ist"].map(TEMPORAL_FACTORS)
    df.loc[df["is_weekend"], "temporal_factor"] *= WEEKEND_MULTIPLIER

    # Peak period label
    df["peak_period"] = df["hour_ist"].apply(_classify_peak_period)

    # Enforcement activity flag (from EDA #1 enforcement gap analysis)
    df["enforcement_active"] = df["hour_ist"].apply(_enforcement_active_score)

    # --- Validation status ---
    df["is_approved"] = df["validation_status"].str.strip().str.lower() == "approved"

    # --- Repeat offender scoring ---
    veh_counts = df["vehicle_number"].value_counts()
    df["repeat_count"] = df["vehicle_number"].map(veh_counts).fillna(1).astype(int)
    max_repeat = max(veh_counts.max(), 2)  # Avoid log(1) = 0
    df["repeat_score"] = np.clip(np.log2(df["repeat_count"]) / np.log2(max_repeat), 0, 1)
    df["is_chronic_offender"] = df["repeat_count"] >= 11

    elapsed = time.perf_counter() - start
    logger.info("Loaded %d violations in %.1fs", len(df), elapsed)

    # Validation
    if not (250_000 < len(df) < 350_000):
        msg = f"Expected ~298K violations, got {len(df)}. Check data file."
        raise DataValidationError(msg)

    return df


def load_road_network(cache_path: Path) -> tuple[nx.MultiDiGraph, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load OSM road network from cached GraphML.

    Args:
        cache_path: Path to the saved .graphml file.

    Returns:
        Tuple of (graph, nodes_gdf, edges_gdf) where edges are enriched
        with road hierarchy attributes and midpoint coordinates.

    Raises:
        FileNotFoundError: If the GraphML file doesn't exist.
    """
    import osmnx as ox

    cache_path = Path(cache_path)
    if not cache_path.exists():
        msg = f"Road network file not found: {cache_path}. Run eda_04_osm_roads.py first."
        raise FileNotFoundError(msg)

    logger.info("Loading road network from %s", cache_path.name)
    start = time.perf_counter()

    graph = ox.load_graphml(cache_path)
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(graph)

    # --- Clean highway column (can be list) ---
    edges_gdf["highway_clean"] = edges_gdf["highway"].apply(_clean_highway_type)

    # --- Apply road hierarchy ---
    hierarchy_data = edges_gdf["highway_clean"].apply(lambda h: ROAD_HIERARCHY.get(h, DEFAULT_ROAD_INFO))
    edges_gdf["road_tier"] = hierarchy_data.apply(lambda d: d["tier"])
    edges_gdf["road_tier_name"] = hierarchy_data.apply(lambda d: d["name"])
    edges_gdf["est_lanes"] = hierarchy_data.apply(lambda d: d["est_lanes"])
    edges_gdf["est_width_m"] = hierarchy_data.apply(lambda d: d["est_width_m"])
    edges_gdf["road_importance"] = hierarchy_data.apply(lambda d: d["importance"])

    # --- Parse actual lanes and width from OSM where available ---
    edges_gdf["parsed_lanes"] = edges_gdf.get("lanes", pd.Series(dtype=float)).apply(_parse_osm_numeric)
    edges_gdf["parsed_width"] = edges_gdf.get("width", pd.Series(dtype=float)).apply(_parse_osm_numeric)

    # Use parsed values where available, fallback to estimates
    edges_gdf["road_lanes"] = edges_gdf["parsed_lanes"].fillna(edges_gdf["est_lanes"]).astype(int)
    edges_gdf["road_width"] = edges_gdf["parsed_width"].fillna(edges_gdf["est_width_m"])

    # --- Road name ---
    edges_gdf["road_name"] = edges_gdf.get("name", pd.Series(dtype=str)).apply(_clean_road_name)

    # --- Edge midpoints ---
    midpoints = edges_gdf["geometry"].apply(lambda g: g.interpolate(0.5, normalized=True))
    edges_gdf["mid_lat"] = midpoints.apply(lambda p: p.y)
    edges_gdf["mid_lon"] = midpoints.apply(lambda p: p.x)

    # --- Link road flag ---
    edges_gdf["is_link_road"] = edges_gdf["highway_clean"].str.endswith("_link")

    # --- Edge length in meters ---
    if "length" in edges_gdf.columns:
        edges_gdf["road_length_m"] = edges_gdf["length"].astype(float)
    else:
        edges_gdf["road_length_m"] = edges_gdf["geometry"].length * LON_TO_METERS

    # --- Segment degree (number of connections at each endpoint) ---
    # For each edge (u, v), compute max(degree(u), degree(v)) as a proxy
    # for how connected the edge's endpoints are.
    edge_degrees = {}
    for node in graph.nodes():
        edge_degrees[node] = graph.degree(node)
    edges_gdf["segment_degree"] = [max(edge_degrees.get(u, 0), edge_degrees.get(v, 0)) for u, v, _ in edges_gdf.index]

    elapsed = time.perf_counter() - start
    logger.info(
        "Loaded road network: %d nodes, %d edges in %.1fs",
        len(nodes_gdf),
        len(edges_gdf),
        elapsed,
    )

    return graph, nodes_gdf, edges_gdf


def load_events(path: Path) -> pd.DataFrame:
    """Load and clean ASTraM event data.

    Args:
        path: Path to the event CSV file.

    Returns:
        Cleaned event DataFrame with IST features.
    """
    path = Path(path)
    if not path.exists():
        msg = f"Event CSV not found: {path}"
        raise FileNotFoundError(msg)

    logger.info("Loading events from %s", path.name)

    df = pd.read_csv(path, low_memory=False)

    # Parse timestamps
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
    df = df.dropna(subset=["start_datetime", "latitude", "longitude"])

    # Filter to Bengaluru bbox
    bbox_mask = (
        (df["latitude"] >= BBOX["lat_min"])
        & (df["latitude"] <= BBOX["lat_max"])
        & (df["longitude"] >= BBOX["lon_min"])
        & (df["longitude"] <= BBOX["lon_max"])
    )
    df = df[bbox_mask].copy()

    # IST conversion
    df["start_datetime_ist"] = df["start_datetime"] + pd.Timedelta(hours=IST_OFFSET_HOURS, minutes=IST_OFFSET_MINUTES)
    df["hour_ist"] = df["start_datetime_ist"].dt.hour
    df["day_of_week"] = df["start_datetime_ist"].dt.dayofweek

    # Cause cleanup
    df["event_cause_clean"] = df["event_cause"].str.strip().str.lower()
    df["is_congestion_event"] = df["event_cause_clean"].isin(
        [
            "congestion",
            "road_accident",
            "vehicle_breakdown",
        ]
    )

    logger.info("Loaded %d events", len(df))
    return df


# =============================================================================
# 2. SPATIAL ENRICHMENT
# =============================================================================


def enrich_violations(
    viol_df: pd.DataFrame,
    edges_gdf: gpd.GeoDataFrame,
    nodes_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Run the full spatial enrichment pipeline on violations.

    Maps each violation to its nearest road segment and computes
    spatial features: road attributes, capacity blocked, junction
    proximity, neighborhood density, and multi-modal proximity.

    Args:
        viol_df: Cleaned violation DataFrame from load_violations().
        edges_gdf: Road edges GeoDataFrame from load_road_network().
        nodes_gdf: Road nodes GeoDataFrame from load_road_network().

    Returns:
        Enriched DataFrame with 40+ features per violation.
    """
    from scipy.spatial import cKDTree

    logger.info("Starting spatial enrichment of %d violations", len(viol_df))
    start = time.perf_counter()

    # =========================================================================
    # Step 1: Map violations to nearest road segment (KDTree)
    # =========================================================================
    logger.info("Step 1/5: KDTree nearest-road matching")
    edge_coords = np.column_stack(
        [
            edges_gdf["mid_lat"].values * LAT_TO_METERS,
            edges_gdf["mid_lon"].values * LON_TO_METERS,
        ]
    )
    viol_coords = np.column_stack(
        [
            viol_df["latitude"].values * LAT_TO_METERS,
            viol_df["longitude"].values * LON_TO_METERS,
        ]
    )

    tree = cKDTree(edge_coords)
    distances, indices = tree.query(viol_coords, k=1)

    viol_df = viol_df.copy()
    viol_df["nearest_edge_idx"] = indices
    viol_df["dist_to_road_m"] = distances

    # Map road attributes
    for col in [
        "highway_clean",
        "road_tier",
        "road_tier_name",
        "road_lanes",
        "road_width",
        "road_importance",
        "road_name",
        "is_link_road",
        "road_length_m",
        "segment_degree",
        "mid_lat",
        "mid_lon",
    ]:
        viol_df[col] = edges_gdf[col].iloc[indices].values

    # Rename midpoint columns for clarity
    viol_df = viol_df.rename(columns={"mid_lat": "road_mid_lat", "mid_lon": "road_mid_lon"})

    # Capacity blocked
    viol_df["capacity_blocked_pct"] = np.clip((viol_df["vehicle_width_m"] / viol_df["road_width"]) * 100, 0, 100)
    viol_df["lanes_blocked"] = np.clip(
        viol_df["vehicle_width_m"] / (viol_df["road_width"] / viol_df["road_lanes"]),
        0,
        viol_df["road_lanes"],
    )

    # =========================================================================
    # Step 2: Junction proximity
    # =========================================================================
    logger.info("Step 2/5: Junction proximity computation")
    node_coords = np.column_stack(
        [
            nodes_gdf["y"].values * LAT_TO_METERS,
            nodes_gdf["x"].values * LON_TO_METERS,
        ]
    )
    junction_tree = cKDTree(node_coords)
    junc_dists, junc_idxs = junction_tree.query(viol_coords, k=1)

    viol_df["dist_to_junction_m"] = junc_dists

    # Get junction degree using street_count from OSMnx if available
    node_sc = nodes_gdf["street_count"].values if "street_count" in nodes_gdf.columns else np.full(len(nodes_gdf), 3)

    viol_df["junction_degree"] = node_sc[junc_idxs]
    viol_df["is_near_major_junction"] = (viol_df["dist_to_junction_m"] < 50) & (viol_df["junction_degree"] >= 4)

    # =========================================================================
    # Step 3: Neighborhood density (count within 300m)
    # =========================================================================
    logger.info("Step 3/5: Neighborhood density computation (chunked to save memory)")
    viol_tree = cKDTree(viol_coords)

    # Process in chunks to avoid OOM — query_ball_point on 298K points
    # at once creates a massive list-of-lists consuming multiple GB of RAM.
    chunk_size = 5000
    n_viols = len(viol_coords)
    density_300m = np.zeros(n_viols, dtype=np.int32)
    for chunk_start in range(0, n_viols, chunk_size):
        chunk_end = min(chunk_start + chunk_size, n_viols)
        chunk_coords = viol_coords[chunk_start:chunk_end]
        chunk_results = viol_tree.query_ball_point(chunk_coords, r=NEIGHBORHOOD_RADIUS_M)
        density_300m[chunk_start:chunk_end] = [len(r) - 1 for r in chunk_results]  # -1 excludes self
        if chunk_start % 50000 == 0:
            logger.info("  Density progress: %d/%d (%.0f%%)", chunk_start, n_viols, chunk_start / n_viols * 100)
    viol_df["violation_density_300m"] = density_300m
    logger.info("  Density 300m complete. Mean density: %.1f", density_300m.mean())

    # Also compute 500m density for cross-reference with grid EDA (plan §1.2.3)
    density_500m = np.zeros(n_viols, dtype=np.int32)
    for chunk_start in range(0, n_viols, chunk_size):
        chunk_end = min(chunk_start + chunk_size, n_viols)
        chunk_coords = viol_coords[chunk_start:chunk_end]
        chunk_results = viol_tree.query_ball_point(chunk_coords, r=NEIGHBORHOOD_RADIUS_500M)
        density_500m[chunk_start:chunk_end] = [len(r) - 1 for r in chunk_results]
    viol_df["violation_density_500m"] = density_500m
    logger.info("  Density 500m complete. Mean density: %.1f", density_500m.mean())

    # =========================================================================
    # Step 4: Multi-modal enrichment (bus stops, metro stations)
    # =========================================================================
    logger.info("Step 4/5: Multi-modal enrichment (bus stops, metro)")
    viol_df = _enrich_multimodal(viol_df, edges_gdf, nodes_gdf)

    # =========================================================================
    # Step 5: Final computed columns
    # =========================================================================
    logger.info("Step 5/5: Computing final features")

    # Road type simplified
    viol_df["road_type_simple"] = viol_df["highway_clean"].apply(
        lambda h: h.replace("_link", "") if isinstance(h, str) else "other"
    )

    # High-impact flag (from EDA #4: blocks >25% of road width)
    viol_df["is_high_impact"] = viol_df["capacity_blocked_pct"] > 25

    elapsed = time.perf_counter() - start
    logger.info(
        "Enrichment complete in %.1fs. Final shape: %s, columns: %d",
        elapsed,
        viol_df.shape,
        len(viol_df.columns),
    )

    return viol_df


# =============================================================================
# 3. MULTI-MODAL ENRICHMENT
# =============================================================================


def _enrich_multimodal(
    viol_df: pd.DataFrame,
    edges_gdf: gpd.GeoDataFrame,
    nodes_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Add bus stop and metro station proximity features.

    Uses OSM node tags to identify transit stops within the road network.
    Falls back to known metro station coordinates if OSM data is sparse.

    Args:
        viol_df: Violations with lat/lon columns.
        edges_gdf: Road edges GeoDataFrame.
        nodes_gdf: Road nodes GeoDataFrame.

    Returns:
        viol_df with additional transit proximity columns.
    """
    from scipy.spatial import cKDTree

    viol_coords = np.column_stack(
        [
            viol_df["latitude"].values * LAT_TO_METERS,
            viol_df["longitude"].values * LON_TO_METERS,
        ]
    )

    # --- Known Namma Metro stations (Green + Purple lines) ---
    metro_stations = _get_metro_stations()
    if len(metro_stations) > 0:
        metro_coords = np.column_stack(
            [
                np.array([s[0] for s in metro_stations]) * LAT_TO_METERS,
                np.array([s[1] for s in metro_stations]) * LON_TO_METERS,
            ]
        )
        metro_tree = cKDTree(metro_coords)
        metro_dists, _ = metro_tree.query(viol_coords, k=1)
        viol_df["dist_to_metro_m"] = metro_dists
        viol_df["is_near_metro"] = metro_dists < METRO_STATION_RADIUS_M
    else:
        viol_df["dist_to_metro_m"] = np.nan
        viol_df["is_near_metro"] = False

    # --- Bus stop proximity (from OSM highway=bus_stop tags in nodes) ---
    # OSMnx may not include bus stops in driving network. Use known stops or flag.
    bus_stop_tags = _get_bmtc_bus_stop_coords(nodes_gdf)
    if len(bus_stop_tags) > 0:
        bus_coords = np.column_stack(
            [
                np.array([b[0] for b in bus_stop_tags]) * LAT_TO_METERS,
                np.array([b[1] for b in bus_stop_tags]) * LON_TO_METERS,
            ]
        )
        bus_tree = cKDTree(bus_coords)
        bus_dists, _ = bus_tree.query(viol_coords, k=1)
        viol_df["dist_to_bus_stop_m"] = bus_dists
        viol_df["is_near_bus_stop"] = bus_dists < BUS_STOP_RADIUS_M
    else:
        # Fallback: use violation type as proxy
        viol_df["dist_to_bus_stop_m"] = np.nan
        viol_df["is_near_bus_stop"] = viol_df["violation_types_list"].apply(lambda vt: any("BUSTOP" in v for v in vt))
        logger.warning("No bus stop data found in OSM. Using violation type as proxy.")

    return viol_df


def _get_metro_stations() -> list[tuple[float, float]]:
    """Return known Namma Metro station coordinates (lat, lon).

    Covers Green Line (Nagasandra to Silk Institute) and
    Purple Line (Whitefield to Kengeri).

    Returns:
        List of (latitude, longitude) tuples for each station.
    """
    return [
        # Green Line (partial — major stations)
        (13.0357, 77.5970),  # Nagasandra
        (13.0193, 77.5957),  # Yeshwanthpur
        (12.9981, 77.5723),  # Majestic (interchange)
        (12.9857, 77.5707),  # Chickpete
        (12.9752, 77.5731),  # KR Market
        (12.9527, 77.5735),  # Lalbagh
        (12.9345, 77.5803),  # Jayanagar
        (12.9166, 77.5829),  # Banashankari
        (12.9056, 77.5856),  # JP Nagar
        (12.8888, 77.5926),  # Silk Institute
        # Purple Line (partial — major stations)
        (12.9961, 77.5097),  # Kengeri
        (12.9918, 77.5370),  # Mysore Road
        (12.9923, 77.5586),  # Magadi Road
        (12.9977, 77.5667),  # City Railway Station
        (12.9981, 77.5723),  # Majestic (interchange, same as above)
        (13.0018, 77.5915),  # MG Road
        (13.0095, 77.6062),  # Indiranagar
        (13.0120, 77.6421),  # Swami Vivekananda Road
        (13.0114, 77.6571),  # Baiyappanahalli
        (12.9932, 77.7030),  # KR Puram
        (12.9770, 77.7230),  # Kadugodi
        (12.9762, 77.7433),  # Whitefield
    ]


def _get_bmtc_bus_stop_coords(
    nodes_gdf: gpd.GeoDataFrame,
) -> list[tuple[float, float]]:
    """Extract bus stop coordinates from OSM node data if available.

    Args:
        nodes_gdf: OSM nodes GeoDataFrame.

    Returns:
        List of (lat, lon) tuples for bus stops.
    """
    # OSMnx driving network typically won't have bus stop nodes,
    # but check for any tagged nodes
    bus_stops: list[tuple[float, float]] = []
    if "highway" in nodes_gdf.columns:
        mask = nodes_gdf["highway"] == "bus_stop"
        if mask.any():
            bus_stops = list(
                zip(
                    nodes_gdf.loc[mask, "y"].values,
                    nodes_gdf.loc[mask, "x"].values,
                    strict=True,
                )
            )
            logger.info("Found %d bus stops in OSM data", len(bus_stops))
    return bus_stops


# =============================================================================
# 4. HELPER FUNCTIONS
# =============================================================================


def _parse_violation_types(raw: str) -> list[str]:
    """Parse violation_type field which may be JSON array or plain string.

    Args:
        raw: Raw violation_type value from CSV.

    Returns:
        List of violation type strings, uppercase.
    """
    if pd.isna(raw) or not isinstance(raw, str):
        return ["UNKNOWN"]

    raw = raw.strip()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(v).strip().upper() for v in parsed if v]
        except (json.JSONDecodeError, ValueError):
            pass

    return [raw.strip().strip('"').upper()]


def _clean_highway_type(highway: object) -> str:
    """Clean OSM highway type which may be a list.

    Args:
        highway: Raw highway value from OSM (str or list).

    Returns:
        Single highway type string.
    """
    if isinstance(highway, list):
        return str(highway[0])
    if pd.isna(highway):
        return "unclassified"
    return str(highway)


def _clean_road_name(name: object) -> str:
    """Clean OSM road name which may be a list or NaN.

    Args:
        name: Raw name value from OSM.

    Returns:
        Cleaned road name string or 'Unnamed'.
    """
    if isinstance(name, list):
        return str(name[0])
    if pd.isna(name) or not isinstance(name, str):
        return "Unnamed"
    return str(name).strip()


def _parse_osm_numeric(val: object) -> float | None:
    """Parse OSM lane/width values which may be strings like '2' or '3;4'.

    Args:
        val: Raw value from OSM tags. Can be int, float, str, list, or NaN.

    Returns:
        Float value, or None if unparseable.
    """
    if val is None:
        return None
    if isinstance(val, list):
        # OSM sometimes stores lanes as ['2', '3'] — take first
        return _parse_osm_numeric(val[0]) if len(val) > 0 else None
    if isinstance(val, (int, float)):
        import math

        return None if math.isnan(val) else float(val)
    if isinstance(val, str):
        # Handle "2;3" → take first
        parts = val.replace(",", ";").split(";")
        try:
            return float(parts[0].strip())
        except ValueError:
            return None
    # For any other type, try to check NaN safely
    try:
        if pd.isna(val):
            return None
    except (ValueError, TypeError):
        pass
    return None


def _classify_peak_period(hour: int) -> str:
    """Classify an IST hour into peak period category.

    Args:
        hour: Hour of day (0-23) in IST.

    Returns:
        One of 'morning_peak', 'midday', 'evening_peak', 'night'.
    """
    if 8 <= hour <= 9:
        return "morning_peak"
    if 10 <= hour <= 16:
        return "midday"
    if 17 <= hour <= 19:
        return "evening_peak"
    return "night"


def _enforcement_active_score(hour: int) -> float:
    """Compute enforcement activity score for an IST hour.

    Based on EDA #1 finding: enforcement gap from 3:30-8:30 PM IST.

    Args:
        hour: Hour of day (0-23) in IST.

    Returns:
        Score between 0 (no enforcement) and 1 (full enforcement).
    """
    if 6 <= hour <= 12:
        return 1.0
    if 16 <= hour <= 20:  # 3:30 PM - 8:30 PM gap
        return 0.1
    if 13 <= hour <= 15:
        return 0.5
    return 0.2  # Night hours
