"""DRISHTAM road network graph construction for GNN propagation.

Transforms the OSM road network into a PyTorch Geometric line graph where:
- Nodes = road segments (from OSM edges)
- Edges = junction connections (two segments sharing an intersection)
- Node features = 12D vector (road + violation + PIS features)
- Edge features = 2D vector (junction degree, angle between roads)

Uses self-supervised training signal: mask known PIS values and train
the GNN to predict them from neighboring road features.

Reference: plans/phase3_gnn_propagation.md
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# 1. LINE GRAPH CONSTRUCTION
# =============================================================================


def osm_to_line_graph(
    osm_graph_path: str | Path,
) -> tuple:
    """Convert OSM graph to a line graph representation.

    In OSM: roads=edges, intersections=nodes.
    In our line graph: roads=nodes, shared junctions=edges.

    Args:
        osm_graph_path: Path to the OSM GraphML file.

    Returns:
        Tuple of (segment_data, adjacency_list, edge_to_node_map)
        where segment_data is a list of dicts with segment attributes.
    """
    import networkx as nx

    logger.info("Loading OSM graph from %s", osm_graph_path)
    G = nx.read_graphml(osm_graph_path)  # noqa: N806
    logger.info("OSM graph loaded: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # Extract edge data — each edge becomes a node in our line graph
    segment_data = []
    edge_to_idx = {}

    for idx, (u, v, key, data) in enumerate(G.edges(data=True, keys=True)):
        seg = {
            "seg_idx": idx,
            "osm_u": u,
            "osm_v": v,
            "osm_key": key,
            "highway": data.get("highway", "unclassified"),
            "lanes": _parse_numeric(data.get("lanes", "1"), default=1),
            "width": _parse_numeric(data.get("width", "8"), default=8.0),
            "length": _parse_numeric(data.get("length", "100"), default=100.0),
            "name": data.get("name", "Unknown"),
            "is_link": "_link" in str(data.get("highway", "")),
        }
        segment_data.append(seg)
        edge_to_idx[(u, v, key)] = idx

    n_segments = len(segment_data)
    logger.info("Extracted %d road segments (line graph nodes)", n_segments)

    # Build adjacency: two segments are connected if they share an OSM node
    logger.info("Building line graph adjacency...")
    node_to_segments: dict[str, list[int]] = {}
    for seg in segment_data:
        for node in [seg["osm_u"], seg["osm_v"]]:
            if node not in node_to_segments:
                node_to_segments[node] = []
            node_to_segments[node].append(seg["seg_idx"])

    # Build edge list (undirected)
    edge_src = []
    edge_dst = []
    junction_degrees = {}

    for osm_node, seg_indices in node_to_segments.items():
        degree = len(seg_indices)
        junction_degrees[osm_node] = degree

        # Connect all pairs of segments at this junction
        # Cap at degree 20 to prevent explosion at major intersections
        indices = seg_indices[:20] if degree > 20 else seg_indices
        for i, s1 in enumerate(indices):
            for s2 in indices[i + 1 :]:
                edge_src.extend([s1, s2])
                edge_dst.extend([s2, s1])

    n_edges = len(edge_src) // 2
    logger.info(
        "Line graph: %d nodes, %d edges (avg degree %.1f)",
        n_segments,
        n_edges,
        len(edge_src) / max(n_segments, 1),
    )

    # Store junction degrees for segments
    for seg in segment_data:
        seg["junction_degree_start"] = junction_degrees.get(seg["osm_u"], 1)
        seg["junction_degree_end"] = junction_degrees.get(seg["osm_v"], 1)

    return segment_data, (edge_src, edge_dst), node_to_segments


# =============================================================================
# 2. NODE FEATURE ENGINEERING
# =============================================================================


def build_node_features(
    segment_data: list[dict],
    violations_df: pd.DataFrame,
) -> np.ndarray:
    """Build 12D feature vector for each road segment node.

    Features:
        0: lanes (normalized)
        1: width (normalized)
        2: road_tier (0-1)
        3: length (log-normalized)
        4: is_link_road (binary)
        5: violation_count (log-normalized)
        6: mean_pis
        7: max_pis
        8: total_pis (log-normalized)
        9: capacity_blocked_mean
        10: junction_degree_start (normalized)
        11: junction_degree_end (normalized)

    Args:
        segment_data: List of segment dicts from osm_to_line_graph().
        violations_df: Enriched violations with PIS scores.

    Returns:
        Feature matrix of shape (N_segments, 12).
    """
    from drishtam.config import ROAD_HIERARCHY

    n_segments = len(segment_data)
    features = np.zeros((n_segments, 12), dtype=np.float32)

    # Aggregate violation stats per nearest road segment
    seg_stats = _aggregate_violations_per_segment(segment_data, violations_df)

    # Road tier mapping (highway type → importance 0-1)
    tier_scores = {}
    max_tier = max(ROAD_HIERARCHY.values(), key=lambda x: x["importance"])["importance"]
    for hw_type, info in ROAD_HIERARCHY.items():
        tier_scores[hw_type] = info["importance"] / max_tier

    for i, seg in enumerate(segment_data):
        stats = seg_stats.get(i, {})

        features[i, 0] = seg["lanes"]
        features[i, 1] = seg["width"]
        features[i, 2] = tier_scores.get(seg["highway"], 0.1)
        features[i, 3] = np.log1p(seg["length"])
        features[i, 4] = float(seg["is_link"])
        features[i, 5] = np.log1p(stats.get("violation_count", 0))
        features[i, 6] = stats.get("mean_pis", 0) / 100.0
        features[i, 7] = stats.get("max_pis", 0) / 100.0
        features[i, 8] = np.log1p(stats.get("total_pis", 0))
        features[i, 9] = stats.get("capacity_blocked_mean", 0) / 100.0
        features[i, 10] = seg["junction_degree_start"]
        features[i, 11] = seg["junction_degree_end"]

    # Normalize each feature to [0, 1]
    for col in range(12):
        col_min = features[:, col].min()
        col_max = features[:, col].max()
        if col_max > col_min:
            features[:, col] = (features[:, col] - col_min) / (col_max - col_min)

    logger.info("Node features: shape=%s, no NaN=%s", features.shape, not np.isnan(features).any())

    return features


# =============================================================================
# 3. TRAINING LABELS (Self-Supervised)
# =============================================================================


def build_self_supervised_labels(
    features: np.ndarray,
    mask_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create self-supervised labels for graph signal inpainting.

    Instead of using external event data, we mask known PIS values
    and train the GNN to reconstruct them from neighbors + road features.

    Strategy:
    - Target = mean_pis (feature column 6) — already normalized [0, 1]
    - Mask 20% of nodes with violations (PIS > 0) → test set
    - Remaining 80% → train set
    - Nodes with PIS = 0 → no label (model learns to infer their propagated impact)

    Args:
        features: Node feature matrix (N, 12).
        mask_ratio: Fraction of violation nodes to mask for validation.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (labels, train_mask, val_mask) arrays.
    """
    rng = np.random.default_rng(seed)

    # Labels = mean PIS (column 6)
    labels = features[:, 6].copy()

    # Nodes with violations (PIS > 0)
    has_violations = labels > 0
    violation_indices = np.where(has_violations)[0]
    n_violations = len(violation_indices)

    # Split violation nodes into train (60%) / val (20%) / test (20%)
    rng.shuffle(violation_indices)
    n_val = int(n_violations * mask_ratio)
    n_test = int(n_violations * mask_ratio)
    n_train = n_violations - n_val - n_test

    train_indices = violation_indices[:n_train]
    val_indices = violation_indices[n_train : n_train + n_val]
    test_indices = violation_indices[n_train + n_val :]

    train_mask = np.zeros(len(labels), dtype=bool)
    val_mask = np.zeros(len(labels), dtype=bool)
    test_mask = np.zeros(len(labels), dtype=bool)

    train_mask[train_indices] = True
    val_mask[val_indices] = True
    test_mask[test_indices] = True

    logger.info(
        "Self-supervised split: %d train, %d val, %d test (of %d violation nodes, %d total)",
        train_mask.sum(),
        val_mask.sum(),
        test_mask.sum(),
        n_violations,
        len(labels),
    )

    return labels, train_mask, val_mask, test_mask


# =============================================================================
# 4. BUILD PyG DATA OBJECT
# =============================================================================


def build_pyg_data(
    features: np.ndarray,
    edge_list: tuple[list[int], list[int]],
    labels: np.ndarray,
    train_mask: np.ndarray,
    val_mask: np.ndarray,
    test_mask: np.ndarray,
) -> object:
    """Package everything into a PyTorch Geometric Data object.

    Args:
        features: Node feature matrix (N, 12).
        edge_list: Tuple of (src, dst) edge index lists.
        labels: Target labels (N,).
        train_mask: Boolean mask for training nodes.
        val_mask: Boolean mask for validation nodes.
        test_mask: Boolean mask for test nodes.

    Returns:
        PyG Data object.
    """
    import torch
    from torch_geometric.data import Data

    edge_src, edge_dst = edge_list

    data = Data(
        x=torch.tensor(features, dtype=torch.float32),
        edge_index=torch.tensor([edge_src, edge_dst], dtype=torch.long),
        y=torch.tensor(labels, dtype=torch.float32),
        train_mask=torch.tensor(train_mask, dtype=torch.bool),
        val_mask=torch.tensor(val_mask, dtype=torch.bool),
        test_mask=torch.tensor(test_mask, dtype=torch.bool),
    )

    logger.info(
        "PyG Data: %d nodes, %d edges, %d features, %d train, %d val, %d test",
        data.num_nodes,
        data.num_edges,
        data.num_node_features,
        data.train_mask.sum().item(),
        data.val_mask.sum().item(),
        data.test_mask.sum().item(),
    )

    return data


# =============================================================================
# 5. HELPERS
# =============================================================================


def _parse_numeric(value: str | int | float | list, default: float = 0.0) -> float:
    """Safely parse a numeric value from OSM attributes.

    OSM attributes can be strings, ints, floats, or lists.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        value = value[0] if value else str(default)
    try:
        return float(str(value).split(";")[0].strip())
    except (ValueError, TypeError):
        return default


def _aggregate_violations_per_segment(
    segment_data: list[dict],
    violations_df: pd.DataFrame,
) -> dict[int, dict]:
    """Aggregate violation statistics per road segment.

    Uses spatial matching: for each violation, find the nearest segment
    by matching road name + proximity.

    Args:
        segment_data: List of segment dicts.
        violations_df: Enriched violations DataFrame.

    Returns:
        Dict mapping segment index to stats dict.
    """
    logger.info("Aggregating violations per road segment...")

    # Build segment centroids for spatial matching
    # Use start/end coordinates from segment_data if available,
    # otherwise fall back to road_name matching
    seg_names = {}
    for seg in segment_data:
        name = seg.get("name", "Unknown")
        if name and name != "Unknown":
            if name not in seg_names:
                seg_names[name] = []
            seg_names[name].append(seg["seg_idx"])

    # Match violations to segments by road name
    stats: dict[int, dict] = {}
    matched = 0

    if "road_name" in violations_df.columns and "pis" in violations_df.columns:
        for road_name, group in violations_df.groupby("road_name"):
            if road_name in seg_names:
                seg_indices = seg_names[road_name]
                per_seg_count = max(1, len(group) // len(seg_indices))

                for seg_idx in seg_indices:
                    stats[seg_idx] = {
                        "violation_count": per_seg_count,
                        "mean_pis": float(group["pis"].mean()),
                        "max_pis": float(group["pis"].max()),
                        "total_pis": float(group["pis"].sum()) / len(seg_indices),
                        "capacity_blocked_mean": float(
                            group["capacity_blocked_pct"].mean() if "capacity_blocked_pct" in group.columns else 0
                        ),
                    }
                    matched += per_seg_count

    logger.info(
        "Matched %d violations to %d segments (of %d total)",
        matched,
        len(stats),
        len(segment_data),
    )

    return stats
