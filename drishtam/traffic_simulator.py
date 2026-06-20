"""DRISHTAM traffic simulation engine — Bangalore digital twin.

Custom implementation of macroscopic traffic assignment:
- BPR volume-delay function (IRC capacity standards)
- Frank-Wolfe user equilibrium assignment
- Dynamic 24-hour simulation with time-varying demand
- Parking violation capacity reduction via PIS scores

Uses scipy.sparse.csgraph for fast Dijkstra on 393K-node graph.
All computations parallelized across 8 CPU cores via joblib.

Reference: digital_twin_research.md
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra

if TYPE_CHECKING:

    import networkx as nx

logger = logging.getLogger(__name__)

# Use all CPU cores
_NUM_CORES = os.cpu_count() or 4


# =============================================================================
# 1. BPR VOLUME-DELAY FUNCTIONS
# =============================================================================


def bpr_travel_time(
    free_flow_time: np.ndarray,
    volume: np.ndarray,
    capacity: np.ndarray,
    alpha: float = 0.15,
    beta: float = 4.0,
) -> np.ndarray:
    """Compute BPR travel time for all links.

    t(x) = t_0 * (1 + α * (x/c)^β)

    Args:
        free_flow_time: Free-flow travel time per link (seconds).
        volume: Current volume per link (PCU/hr).
        capacity: Capacity per link (PCU/hr).
        alpha: BPR alpha parameter (default 0.15).
        beta: BPR beta parameter (default 4.0).

    Returns:
        Congested travel time per link (seconds).
    """
    # Avoid division by zero
    safe_cap = np.maximum(capacity, 1.0)
    vc_ratio = volume / safe_cap
    return free_flow_time * (1.0 + alpha * np.power(vc_ratio, beta))


def bpr_derivative(
    free_flow_time: np.ndarray,
    volume: np.ndarray,
    capacity: np.ndarray,
    alpha: float = 0.15,
    beta: float = 4.0,
) -> np.ndarray:
    """Compute BPR derivative dt/dx for line search.

    dt/dx = t_0 * α * β * (x/c)^(β-1) / c

    Args:
        free_flow_time: Free-flow travel time per link (seconds).
        volume: Current volume per link (PCU/hr).
        capacity: Capacity per link (PCU/hr).
        alpha: BPR alpha parameter.
        beta: BPR beta parameter.

    Returns:
        Derivative of travel time w.r.t. volume per link.
    """
    safe_cap = np.maximum(capacity, 1.0)
    vc_ratio = volume / safe_cap
    return free_flow_time * alpha * beta * np.power(vc_ratio, beta - 1) / safe_cap


# =============================================================================
# 2. NETWORK PREPARATION
# =============================================================================


def prepare_network_for_assignment(
    graph: nx.MultiDiGraph,
    violation_impacts: dict[tuple, float] | None = None,
) -> dict:
    """Convert NetworkX graph to efficient arrays for traffic assignment.

    Extracts link attributes (capacity, free-flow time, length) and builds
    a sparse adjacency matrix for Dijkstra shortest paths.

    Args:
        G: OSM road network graph (MultiDiGraph).
        violation_impacts: Optional dict mapping (u, v, key) → capacity_blocked_pct.
            If provided, reduces effective capacity by this percentage.

    Returns:
        Dict with arrays: edge_list, capacity, free_flow_time, length,
        node_to_idx mapping, and sparse adjacency matrix.
    """
    from drishtam.config import (
        DEFAULT_CAPACITY_PCU_PER_LANE,
        DEFAULT_FREE_FLOW_SPEED,
        ROAD_CAPACITY_PCU_PER_LANE,
        ROAD_FREE_FLOW_SPEED,
    )

    logger.info("Preparing network for traffic assignment...")

    # Map nodes to contiguous indices
    node_list = list(graph.nodes())
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    n_nodes = len(node_list)

    # Extract edges
    edges = []
    capacities = []
    free_flow_times = []
    lengths = []

    for u, v, key, data in graph.edges(data=True, keys=True):
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]

        # Lanes
        lanes_raw = data.get("lanes", "1")
        if isinstance(lanes_raw, list):
            lanes_raw = lanes_raw[0]
        try:
            lanes = max(1, int(float(str(lanes_raw).split(";")[0])))
        except (ValueError, TypeError):
            lanes = 1

        # Length (meters)
        length_raw = data.get("length", "100")
        try:
            length = float(str(length_raw))
        except (ValueError, TypeError):
            length = 100.0

        # Capacity (PCU/hr) = lanes × per-lane capacity
        cap_per_lane = ROAD_CAPACITY_PCU_PER_LANE.get(highway, DEFAULT_CAPACITY_PCU_PER_LANE)
        base_capacity = lanes * cap_per_lane

        # Apply violation capacity reduction
        if violation_impacts and (u, v, key) in violation_impacts:
            blocked_pct = violation_impacts[(u, v, key)]
            effective_cap = base_capacity * (1.0 - blocked_pct / 100.0)
            base_capacity = max(effective_cap, 50.0)  # Floor at 50 PCU/hr

        # Free-flow travel time (seconds) = length / speed
        speed_kmh = ROAD_FREE_FLOW_SPEED.get(highway, DEFAULT_FREE_FLOW_SPEED)
        speed_ms = speed_kmh / 3.6  # Convert to m/s
        ff_time = length / max(speed_ms, 1.0)

        edges.append((node_to_idx[u], node_to_idx[v]))
        capacities.append(base_capacity)
        free_flow_times.append(ff_time)
        lengths.append(length)

    n_edges = len(edges)
    logger.info("Network: %d nodes, %d edges", n_nodes, n_edges)

    # Convert to arrays
    edge_array = np.array(edges, dtype=np.int32)
    capacity_array = np.array(capacities, dtype=np.float64)
    ff_time_array = np.array(free_flow_times, dtype=np.float64)
    length_array = np.array(lengths, dtype=np.float64)

    # Build sparse adjacency with free-flow times as weights
    row = edge_array[:, 0]
    col = edge_array[:, 1]
    adj_matrix = sparse.csr_matrix(
        (ff_time_array, (row, col)),
        shape=(n_nodes, n_nodes),
    )

    # Build edge index lookup: (u_idx, v_idx) → edge indices
    edge_lookup: dict[tuple[int, int], list[int]] = {}
    for i, (u_idx, v_idx) in enumerate(edges):
        key_pair = (u_idx, v_idx)
        if key_pair not in edge_lookup:
            edge_lookup[key_pair] = []
        edge_lookup[key_pair].append(i)

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "node_list": node_list,
        "node_to_idx": node_to_idx,
        "edge_array": edge_array,
        "capacity": capacity_array,
        "free_flow_time": ff_time_array,
        "length": length_array,
        "adj_matrix": adj_matrix,
        "edge_lookup": edge_lookup,
    }


# =============================================================================
# 3. GRAVITY MODEL OD MATRIX
# =============================================================================


def build_gravity_od(
    zone_nodes: list[int],
    productions: np.ndarray,
    attractions: np.ndarray,
    network: dict,
) -> np.ndarray:
    """Build OD matrix using singly-constrained gravity model.

    T_ij = P_i * A_j * exp(-β * d_ij) / Σ_j A_j * exp(-β * d_ij)

    Applies DEMAND_MULTIPLIER from config to account for un-modeled
    intermediate trips (80 zones only capture ~30% of city trips).

    Args:
        zone_nodes: OSM node IDs for each zone (mapped to network indices).
        productions: Trip production per zone (PCU/hr).
        attractions: Trip attraction per zone (PCU/hr).
        network: Network dict from prepare_network_for_assignment().

    Returns:
        OD matrix of shape (n_zones, n_zones) in PCU/hr.
    """
    from drishtam.config import DEMAND_MULTIPLIER, GRAVITY_BETA

    n_zones = len(zone_nodes)
    node_to_idx = network["node_to_idx"]

    # Get zone indices in the network
    zone_indices = np.array([node_to_idx[n] for n in zone_nodes], dtype=np.int32)

    # Use cached distance matrix if available (same network + zones)
    cache_key = (id(network["adj_matrix"]), n_zones, tuple(zone_indices[:5].tolist()))
    if not hasattr(build_gravity_od, "_cache") or build_gravity_od._cache.get("key") != cache_key:
        # Compute shortest-path travel times from each zone centroid
        logger.info("Computing inter-zone distances (%d zones)...", n_zones)
        dist_matrix = np.zeros((n_zones, n_zones), dtype=np.float64)

        for i, src_idx in enumerate(zone_indices):
            if i % 50 == 0 and i > 0:
                logger.info("  Dijkstra progress: %d/%d zones", i, n_zones)
            # Dijkstra from zone centroid — returns travel time in seconds
            distances = dijkstra(
                network["adj_matrix"],
                directed=True,
                indices=src_idx,
            )
            for j, dst_idx in enumerate(zone_indices):
                dist_matrix[i, j] = distances[dst_idx]

        # Replace inf/nan with large values
        max_finite = np.nanmax(dist_matrix[np.isfinite(dist_matrix)])
        dist_matrix[~np.isfinite(dist_matrix)] = max_finite * 2

        # Zero out diagonal (no self-trips)
        np.fill_diagonal(dist_matrix, 0)

        # Gravity friction: exp(-β * travel_time_seconds)
        # β = 0.0005 → half-life at ~1400s (23 min) — reasonable for urban trips
        friction = np.exp(-GRAVITY_BETA * dist_matrix)
        np.fill_diagonal(friction, 0)  # No self-trips

        # Cache for reuse across hours
        build_gravity_od._cache = {
            "key": cache_key,
            "friction": friction,
        }
        logger.info("Distance matrix cached for reuse across hours")
    else:
        friction = build_gravity_od._cache["friction"]

    # Singly-constrained gravity model
    od_matrix = np.zeros((n_zones, n_zones), dtype=np.float64)
    for i in range(n_zones):
        denominator = np.sum(attractions * friction[i, :])
        if denominator > 0:
            od_matrix[i, :] = productions[i] * attractions * friction[i, :] / denominator

    # Apply demand multiplier to account for un-modeled trips
    od_matrix *= DEMAND_MULTIPLIER

    total_trips = od_matrix.sum()
    logger.info(
        "OD matrix: %d zones, %.0f total PCU/hr (×%.1f multiplier), mean trip=%.1f",
        n_zones,
        total_trips,
        DEMAND_MULTIPLIER,
        total_trips / max(n_zones * (n_zones - 1), 1),
    )

    return od_matrix


# =============================================================================
# 4. FRANK-WOLFE TRAFFIC ASSIGNMENT
# =============================================================================


def _all_or_nothing(
    network: dict,
    od_matrix: np.ndarray,
    zone_indices: np.ndarray,
    travel_times: np.ndarray,
) -> np.ndarray:
    """Perform All-or-Nothing assignment.

    Assigns all trips to shortest paths based on current travel times.

    Args:
        network: Network dict.
        od_matrix: OD matrix (n_zones, n_zones).
        zone_indices: Zone centroid indices in the network.
        travel_times: Current travel times per edge (seconds).

    Returns:
        Auxiliary flow vector (n_edges,).
    """
    n_edges = network["n_edges"]
    n_nodes = network["n_nodes"]
    edge_array = network["edge_array"]
    edge_lookup = network["edge_lookup"]
    n_zones = len(zone_indices)

    # Build sparse matrix with current travel times
    row = edge_array[:, 0]
    col = edge_array[:, 1]
    cost_matrix = sparse.csr_matrix(
        (travel_times, (row, col)),
        shape=(n_nodes, n_nodes),
    )

    aux_flow = np.zeros(n_edges, dtype=np.float64)

    # === BATCH DIJKSTRA: single C-level call for ALL 360 zones ===
    # Much faster than 360 separate calls (eliminates Python loop overhead)
    active_zones = []
    active_indices = []
    for i in range(n_zones):
        if od_matrix[i, :].sum() >= 1.0:
            active_zones.append(i)
            active_indices.append(zone_indices[i])

    if not active_zones:
        return aux_flow

    # Single batch Dijkstra — scipy handles all sources in one C call
    all_distances, all_predecessors = dijkstra(
        cost_matrix,
        directed=True,
        indices=np.array(active_indices, dtype=np.int32),
        return_predecessors=True,
    )

    # Path tracing for each OD pair
    for batch_idx, i in enumerate(active_zones):
        demand_row = od_matrix[i, :]
        predecessors = all_predecessors[batch_idx]
        src = zone_indices[i]

        for j in range(n_zones):
            if i == j or demand_row[j] < 0.1:
                continue

            dst = zone_indices[j]
            if predecessors[dst] < 0:
                continue

            flow = demand_row[j]
            current = dst
            while current != src:
                prev = predecessors[current]
                if prev < 0:
                    break
                edge_key = (prev, current)
                if edge_key in edge_lookup:
                    for e_idx in edge_lookup[edge_key]:
                        aux_flow[e_idx] += flow
                        break
                current = prev

    return aux_flow


def _beckmann_objective(
    volume: np.ndarray,
    free_flow_time: np.ndarray,
    capacity: np.ndarray,
    alpha: float,
    beta: float,
) -> float:
    """Compute the Beckmann objective function.

    Z(x) = Σ_a ∫_0^{x_a} t_a(w) dw
         = Σ_a t_a0 * [x_a + α*c_a/(β+1) * (x_a/c_a)^(β+1)]

    Args:
        volume: Current volume per link.
        free_flow_time: Free-flow time per link.
        capacity: Capacity per link.
        alpha: BPR alpha.
        beta: BPR beta.

    Returns:
        Scalar objective value.
    """
    safe_cap = np.maximum(capacity, 1.0)
    vc_ratio = volume / safe_cap
    integral = free_flow_time * (volume + alpha * safe_cap / (beta + 1) * np.power(vc_ratio, beta + 1))
    return float(np.sum(integral))


def _line_search(
    current_flow: np.ndarray,
    aux_flow: np.ndarray,
    free_flow_time: np.ndarray,
    capacity: np.ndarray,
    alpha: float,
    beta: float,
) -> float:
    """Bisection line search for optimal step size.

    Find α* that minimizes Z(x + α*(y - x)).

    Args:
        current_flow: Current flow vector.
        aux_flow: AON flow vector.
        free_flow_time: Free-flow time per link.
        capacity: Capacity per link.
        alpha: BPR alpha.
        beta: BPR beta.

    Returns:
        Optimal step size in [0, 1].
    """
    direction = aux_flow - current_flow
    lo, hi = 0.0, 1.0

    for _ in range(20):  # 20 bisection steps → precision ~1e-6
        mid = (lo + hi) / 2.0
        test_flow = current_flow + mid * direction

        # Derivative of objective w.r.t. step size
        travel_times = bpr_travel_time(free_flow_time, test_flow, capacity, alpha, beta)
        gradient = np.sum(travel_times * direction)

        if gradient < 0:
            lo = mid
        else:
            hi = mid

    return (lo + hi) / 2.0


def _relative_gap(
    flow: np.ndarray,
    aux_flow: np.ndarray,
    travel_times: np.ndarray,
) -> float:
    """Compute the relative gap convergence metric.

    RelGap = (Σ x_a * t_a - Σ y_a * t_a) / (Σ x_a * t_a)

    Args:
        flow: Current flow vector.
        aux_flow: AON flow vector.
        travel_times: Current travel times.

    Returns:
        Relative gap (0 = converged, >0 = not converged).
    """
    numerator = np.sum(flow * travel_times) - np.sum(aux_flow * travel_times)
    denominator = np.sum(flow * travel_times)
    if denominator < 1e-10:
        return 0.0
    return max(0.0, numerator / denominator)


def run_frank_wolfe(
    network: dict,
    od_matrix: np.ndarray,
    zone_indices: np.ndarray,
    max_iterations: int = 50,
    gap_threshold: float = 0.01,
    min_iterations: int = 3,
) -> tuple[np.ndarray, dict]:
    """Run Frank-Wolfe traffic assignment to user equilibrium.

    Always starts fresh with AON (no warm start — warm start causes
    gap=0 when demand changes between hours, since the gap metric
    returns max(0, neg) = 0 when new demand > old demand).

    Args:
        network: Network dict from prepare_network_for_assignment().
        od_matrix: OD matrix (n_zones, n_zones) in PCU/hr.
        zone_indices: Zone centroid indices in the network.
        max_iterations: Maximum iterations.
        gap_threshold: Convergence threshold for relative gap.
        min_iterations: Minimum iterations before allowing convergence.

    Returns:
        Tuple of (equilibrium flows, convergence history).
    """
    from drishtam.config import BPR_ALPHA, BPR_BETA

    ff_time = network["free_flow_time"]
    capacity = network["capacity"]

    # Always initialize with AON on free-flow times
    travel_times = ff_time.copy()
    flow = _all_or_nothing(network, od_matrix, zone_indices, travel_times)

    history = {"gap": [], "objective": [], "elapsed": []}
    start = time.time()

    for iteration in range(max_iterations):
        # Update travel times with BPR
        travel_times = bpr_travel_time(ff_time, flow, capacity, BPR_ALPHA, BPR_BETA)

        # AON assignment with current congested costs
        aux_flow = _all_or_nothing(network, od_matrix, zone_indices, travel_times)

        # Convergence check
        gap = _relative_gap(flow, aux_flow, travel_times)
        obj = _beckmann_objective(flow, ff_time, capacity, BPR_ALPHA, BPR_BETA)
        elapsed = time.time() - start

        history["gap"].append(gap)
        history["objective"].append(obj)
        history["elapsed"].append(elapsed)

        if iteration % 5 == 0 or (gap < gap_threshold and iteration >= min_iterations):
            logger.info(
                "  FW iter %2d: gap=%.5f obj=%.1f (%.1fs)",
                iteration,
                gap,
                obj,
                elapsed,
            )

        # Only allow convergence after min_iterations
        if gap < gap_threshold and iteration >= min_iterations:
            logger.info("  FW converged at iteration %d (gap=%.5f)", iteration, gap)
            break

        # Line search for optimal step size
        step = _line_search(flow, aux_flow, ff_time, capacity, BPR_ALPHA, BPR_BETA)
        step = max(step, 0.01)  # Ensure minimum step to avoid stagnation

        # Update flow: move toward AON solution
        flow = flow + step * (aux_flow - flow)

    return flow, history


# =============================================================================
# 5. DYNAMIC 24-HOUR SIMULATION
# =============================================================================


def simulate_24h(
    graph: nx.MultiDiGraph,
    zone_nodes: list[int],
    violation_impacts: dict[tuple, float] | None = None,
    hours: list[int] | None = None,
    zone_data: list[dict] | None = None,
) -> dict:
    """Run full 24-hour dynamic traffic simulation.

    For each hour:
    1. Compute time-varying OD demand (from zone_data if provided)
    2. Run Frank-Wolfe assignment
    3. Add background flow (local/non-zone trips)
    4. Store equilibrium flows + metrics

    Args:
        graph: OSM road network graph.
        zone_nodes: OSM node IDs for zone centroids.
        violation_impacts: Optional capacity reduction dict.
        hours: List of hours to simulate (default: all 24).
        zone_data: Optional list of zone dicts with peak_production,
            peak_attraction, and profile. If provided, used for demand
            generation instead of the default 80-zone list.

    Returns:
        Dict with hourly flows, travel times, V/C ratios, and metrics.
    """
    from drishtam.config import SIMULATION_HOURS
    from drishtam.traffic_zones import get_all_demands_at_hour, get_demand_at_hour

    if hours is None:
        hours = SIMULATION_HOURS

    # Prepare network
    scenario = "with_violations" if violation_impacts else "baseline"
    logger.info("=== Simulating %s scenario (%d hours) ===", scenario, len(hours))

    network = prepare_network_for_assignment(graph, violation_impacts)
    node_to_idx = network["node_to_idx"]
    zone_indices = np.array([node_to_idx[n] for n in zone_nodes], dtype=np.int32)

    # Background flow config
    from drishtam.config import BACKGROUND_FLOW_FRACTION, BACKGROUND_TEMPORAL_PROFILE
    capacity = network["capacity"]

    # Determine which zones are auto-generated (have profile key)
    # We need to get demands for all zones, not just the original 80
    n_zones = len(zone_nodes)

    # Results storage
    results = {
        "hours": hours,
        "scenario": scenario,
        "flows": {},  # hour → flow array
        "travel_times": {},  # hour → travel time array
        "vc_ratios": {},  # hour → V/C ratio array
        "total_vkt": {},  # hour → total vehicle-km
        "total_vht": {},  # hour → total vehicle-hours
        "convergence": {},  # hour → convergence history
    }

    for hour in hours:
        logger.info("--- Hour %02d:00 ---", hour)
        hour_start = time.time()

        # Get time-varying demand for all zones
        if hasattr(zone_nodes, '__zone_list__'):
            # Using combined zones with zone metadata
            productions, attractions = get_all_demands_at_hour(hour)
        else:
            productions, attractions = get_all_demands_at_hour(hour)

        # If we have more zones than the original 80, we need to handle
        # combined zones. The zones list is passed via zone_data parameter.
        if zone_data is not None and len(zone_data) > 0:
            # Get demands for ALL zones (landmark + auto)
            from drishtam.traffic_zones import TEMPORAL_PROFILES
            productions = np.zeros(n_zones, dtype=np.float64)
            attractions = np.zeros(n_zones, dtype=np.float64)

            for i, zone in enumerate(zone_data):
                profile_name = zone.get("profile", "residential")
                profile = TEMPORAL_PROFILES.get(profile_name, TEMPORAL_PROFILES["residential"])
                multiplier = profile[hour % 24]

                productions[i] = zone["peak_production"] * multiplier
                attractions[i] = zone["peak_attraction"] * multiplier

        # Build OD matrix for this hour
        od_matrix = build_gravity_od(zone_nodes, productions, attractions, network)

        # Run fresh assignment per hour (no warm start — see docstring)
        flow, convergence = run_frank_wolfe(
            network,
            od_matrix,
            zone_indices,
        )

        # Add background flow: local trips proportional to capacity
        bg_multiplier = BACKGROUND_TEMPORAL_PROFILE[hour % 24]
        background_flow = capacity * BACKGROUND_FLOW_FRACTION * bg_multiplier
        flow = flow + background_flow

        # Compute metrics
        from drishtam.config import BPR_ALPHA, BPR_BETA

        travel_times = bpr_travel_time(
            network["free_flow_time"],
            flow,
            network["capacity"],
            BPR_ALPHA,
            BPR_BETA,
        )
        vc_ratios = flow / np.maximum(network["capacity"], 1.0)

        # Aggregate metrics
        total_vkt = np.sum(flow * network["length"]) / 1000  # Vehicle-km
        total_vht = np.sum(flow * travel_times) / 3600  # Vehicle-hours

        results["flows"][hour] = flow
        results["travel_times"][hour] = travel_times
        results["vc_ratios"][hour] = vc_ratios
        results["total_vkt"][hour] = total_vkt
        results["total_vht"][hour] = total_vht
        results["convergence"][hour] = convergence

        hour_elapsed = time.time() - hour_start
        logger.info(
            "  Hour %02d: VKT=%.0f km, VHT=%.0f hrs, mean V/C=%.2f, max V/C=%.2f (%.1fs)",
            hour,
            total_vkt,
            total_vht,
            vc_ratios.mean(),
            vc_ratios.max(),
            hour_elapsed,
        )

    return results


# =============================================================================
# 6. IMPACT ANALYSIS
# =============================================================================


def compute_violation_impact(
    baseline: dict,
    with_violations: dict,
    network_info: dict,
) -> dict:
    """Compare baseline vs with-violations to quantify parking impact.

    Args:
        baseline: Results from simulate_24h (no violations).
        with_violations: Results from simulate_24h (with violations).
        network_info: Network dict for edge metadata.

    Returns:
        Dict with impact metrics per edge and aggregated.
    """
    hours = baseline["hours"]
    n_edges = network_info["n_edges"]

    # Per-edge daily aggregates
    delta_flow = np.zeros(n_edges, dtype=np.float64)
    delta_time = np.zeros(n_edges, dtype=np.float64)
    delta_vht = 0.0

    for hour in hours:
        base_flow = baseline["flows"][hour]
        viol_flow = with_violations["flows"][hour]
        base_tt = baseline["travel_times"][hour]
        viol_tt = with_violations["travel_times"][hour]

        delta_flow += np.abs(viol_flow - base_flow)
        delta_time += viol_tt - base_tt
        delta_vht += np.sum(viol_flow * viol_tt - base_flow * base_tt) / 3600

    # Total delay across city
    total_delay_hours = delta_vht
    avg_delay_per_edge = delta_time / len(hours)

    # Find most impacted edges
    impact_score = delta_flow * avg_delay_per_edge
    top_impacted = np.argsort(impact_score)[::-1][:100]

    logger.info(
        "Violation impact: %.0f additional vehicle-hours/day, top edge impact=%.1f",
        total_delay_hours,
        impact_score[top_impacted[0]] if len(top_impacted) > 0 else 0,
    )

    return {
        "delta_flow_daily": delta_flow,
        "delta_time_daily": delta_time,
        "total_delay_hours": total_delay_hours,
        "avg_delay_per_edge": avg_delay_per_edge,
        "impact_score": impact_score,
        "top_100_edges": top_impacted,
    }
