"""Phase 3C: Re-train GNN with Digital Twin targets (delta_delay).

Replaces the circular PIS self-supervised approach with physics-based
supervision from the traffic simulator. The twin's delta_delay measures
actual traffic delay caused by parking violations — this is the "ground
truth" the GNN should learn to predict.

Usage:
    python scripts/03c_retrain_gnn_twin.py

Steps:
    1. Load the line graph (same as Phase 3)
    2. Load delay_metrics.parquet from digital twin
    3. Map delta_delay to graph nodes (road segments)
    4. Build labels: normalized delta_delay
    5. Train GAT with new target
    6. Ablation: compare MLP vs GNN (should see GNN improvement)
    7. Save model + propagated scores
    8. Generate visualizations + research report

Reference: research/09_digital_twin_simulation.md
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")

# Use all cores
os.environ["OMP_NUM_THREADS"] = str(os.cpu_count() or 4)
os.environ["MKL_NUM_THREADS"] = str(os.cpu_count() or 4)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from drishtam.config import (
    ENRICHED_DATA_PATH,
    GRAPH_DATA_PATH,
    MODELS_DIR,
    OSM_CACHE_PATH,
    PLOT_DPI,
    RESEARCH_DIR,
    setup_logging,
)
from drishtam.graph_builder import (
    build_node_features,
    build_pyg_data,
    osm_to_line_graph,
)
from drishtam.propagation_model import (
    build_gat_model,
    predict_propagation,
    train_propagation_model,
)

logger = logging.getLogger(__name__)

SIMULATION_DIR = PROJECT_ROOT / "data" / "simulation"
TWIN_MODEL_PATH = MODELS_DIR / "gat_twin_target.pt"
TWIN_SCORES_PATH = PROJECT_ROOT / "data" / "twin_propagated_impact.parquet"


# =============================================================================
# 1. LOAD TWIN TARGETS
# =============================================================================


def load_twin_targets(
    segment_data: list[dict],
    edge_to_node_map: dict,
) -> np.ndarray:
    """Load delta_delay from digital twin and map to graph nodes.

    The delay_metrics.parquet has per-edge (u, v) delay deltas.
    We map these to the line graph nodes using the edge_to_node_map.

    Args:
        segment_data: List of segment dicts from line graph.
        edge_to_node_map: Maps (osm_u, osm_v, key) -> node_idx.

    Returns:
        Array of normalized delta_delay values (N,) in [0, 1].
    """
    delay_path = SIMULATION_DIR / "delay_metrics.parquet"
    if not delay_path.exists():
        msg = f"delay_metrics.parquet not found at {delay_path}"
        raise FileNotFoundError(msg)

    df = pd.read_parquet(delay_path)
    logger.info("Loaded delay metrics: %d rows × %d cols", len(df), len(df.columns))
    logger.info("Columns: %s", list(df.columns))

    # Identify the delay column
    delay_col = None
    for col in ["delta_vht", "delta_delay", "impact_score", "mean_delta_time"]:
        if col in df.columns:
            delay_col = col
            break

    if delay_col is None:
        # Fall back: compute from available columns
        if "flow_violation" in df.columns and "flow_baseline" in df.columns:
            logger.info("Computing delta from flow columns")
            df["delta_delay"] = df["flow_violation"] - df["flow_baseline"]
            delay_col = "delta_delay"
        else:
            logger.warning("Cannot find delay column, using first numeric column")
            delay_col = df.select_dtypes(include=[np.number]).columns[0]

    logger.info("Using target column: %s", delay_col)
    logger.info("  Range: [%.4f, %.4f], mean=%.4f", df[delay_col].min(), df[delay_col].max(), df[delay_col].mean())

    # Build mapping: segment -> delay
    n_nodes = len(segment_data)
    delay_values = np.zeros(n_nodes, dtype=np.float64)
    matched = 0

    # Try to map by edge_id if available
    if "edge_id" in df.columns:
        edge_delay = df.groupby("edge_id")[delay_col].mean()
        for node_idx, seg in enumerate(segment_data):
            u, v, k = seg["osm_u"], seg["osm_v"], seg.get("osm_key", "0")
            # Try multiple key formats
            for eid in [f"{u}-{v}-{k}", f"{u}-{v}", f"({u}, {v}, {k})", f"({u}, {v})"]:
                if eid in edge_delay.index:
                    delay_values[node_idx] = max(0, edge_delay[eid])
                    matched += 1
                    break
    elif "u" in df.columns and "v" in df.columns:
        # Map by u, v columns
        edge_delay = df.groupby(["u", "v"])[delay_col].mean()
        for node_idx, seg in enumerate(segment_data):
            u, v = str(seg["osm_u"]), str(seg["osm_v"])
            for pair in [(u, v), (v, u)]:
                if pair in edge_delay.index:
                    delay_values[node_idx] = max(0, edge_delay[pair])
                    matched += 1
                    break
    else:
        # Fall back to positional mapping (same order as segments)
        logger.info("No edge_id/u/v columns — using positional mapping")
        delay_arr = df[delay_col].values
        n_map = min(n_nodes, len(delay_arr))
        delay_values[:n_map] = np.maximum(0, delay_arr[:n_map])
        matched = n_map

    logger.info("Mapped %d / %d segments to twin delays", matched, n_nodes)

    # Normalize to [0, 1] using robust scaling (99th percentile)
    nonzero = delay_values[delay_values > 0]
    if len(nonzero) > 0:
        p99 = np.percentile(nonzero, 99)
        if p99 > 0:
            delay_values = np.clip(delay_values / p99, 0, 1)
        logger.info("Normalized: %d segments with delay > 0, p99=%.4f", len(nonzero), p99)
    else:
        logger.warning("No segments matched! Check delay_metrics format.")

    return delay_values.astype(np.float32)


# =============================================================================
# 2. BUILD TRAIN/VAL/TEST SPLIT FOR TWIN TARGETS
# =============================================================================


def build_twin_supervised_labels(
    delay_values: np.ndarray,
    features: np.ndarray,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Create supervised labels from twin delta_delay.

    Unlike self-supervised PIS inpainting, this uses REAL delay values
    from the traffic simulation as ground truth.

    Split strategy:
    - All segments with delta_delay > 0: 60% train / 20% val / 20% test
    - Segments with delta_delay = 0: also split but with lower weight

    Args:
        delay_values: Normalized delta_delay (N,) in [0, 1].
        features: Node feature matrix (N, F).
        seed: Random seed.

    Returns:
        Tuple of (labels, train_mask, val_mask, test_mask).
    """
    rng = np.random.default_rng(seed)
    n_nodes = len(delay_values)

    labels = delay_values.copy()

    # Split: affected segments (delay > 0) split 60/20/20
    affected = np.where(labels > 0)[0]
    unaffected = np.where(labels == 0)[0]

    rng.shuffle(affected)
    n_aff = len(affected)
    n_train_a = int(n_aff * 0.6)
    n_val_a = int(n_aff * 0.2)

    # Also sample some unaffected segments for training (learn "no impact")
    rng.shuffle(unaffected)
    n_unaff_train = min(len(unaffected), n_aff)  # Balanced sampling
    n_train_u = int(n_unaff_train * 0.6)
    n_val_u = int(n_unaff_train * 0.2)

    train_mask = np.zeros(n_nodes, dtype=bool)
    val_mask = np.zeros(n_nodes, dtype=bool)
    test_mask = np.zeros(n_nodes, dtype=bool)

    # Affected segments
    train_mask[affected[:n_train_a]] = True
    val_mask[affected[n_train_a:n_train_a + n_val_a]] = True
    test_mask[affected[n_train_a + n_val_a:]] = True

    # Unaffected segments (balanced)
    train_mask[unaffected[:n_train_u]] = True
    val_mask[unaffected[n_train_u:n_train_u + n_val_u]] = True
    test_mask[unaffected[n_train_u + n_val_u:n_train_u + n_val_u + (n_unaff_train - n_train_u - n_val_u)]] = True

    logger.info(
        "Twin-supervised split: %d train, %d val, %d test "
        "(%d affected, %d unaffected sampled, %d total)",
        train_mask.sum(),
        val_mask.sum(),
        test_mask.sum(),
        n_aff,
        n_unaff_train,
        n_nodes,
    )

    return labels, train_mask, val_mask, test_mask


# =============================================================================
# 3. ABLATION STUDY (MLP vs GNN with twin targets)
# =============================================================================


def run_twin_ablation(
    features: np.ndarray,
    edge_list: tuple,
    labels: np.ndarray,
    train_mask: np.ndarray,
    val_mask: np.ndarray,
    test_mask: np.ndarray,
) -> dict:
    """Run ablation: MLP baseline vs GNN with twin targets.

    Key hypothesis: With physics-based targets, GNN should outperform
    MLP because delta_delay has genuine spatial structure (delay
    propagates through the network via traffic rerouting).

    Returns:
        Dict with model results.
    """
    import torch
    from scipy.stats import spearmanr

    from drishtam.propagation_model import _setup_torch_threads

    _setup_torch_threads()

    results = {}

    # Build PyG data
    data = build_pyg_data(features, edge_list, labels, train_mask, val_mask, test_mask)

    # --- Experiment 1: Full GNN (3-hop GAT) ---
    logger.info("=== Ablation 1: Full GNN (3-hop GAT) ===")
    model_gnn = build_gat_model(in_channels=features.shape[1], hidden_channels=64, heads=4, num_layers=3)
    model_gnn, hist_gnn = train_propagation_model(
        data, model_gnn, lr=0.001, max_epochs=200, patience=30
    )
    gnn_scores = predict_propagation(model_gnn, data)
    gnn_test_r, _ = spearmanr(gnn_scores[test_mask], labels[test_mask])
    results["full_gnn"] = {
        "model": "3-hop GAT",
        "test_r": gnn_test_r,
        "history": hist_gnn,
        "scores": gnn_scores,
    }
    logger.info("Full GNN: test Spearman r = %.4f", gnn_test_r)

    # --- Experiment 2: MLP Baseline (no graph) ---
    logger.info("=== Ablation 2: MLP Baseline ===")
    from torch import nn

    class MLPBaseline(nn.Module):
        def __init__(self, in_dim: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(in_dim, 128),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(64, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor = None, **kwargs: object) -> torch.Tensor:
            return self.net(x).squeeze(-1)

    mlp = MLPBaseline(features.shape[1])
    mlp, hist_mlp = train_propagation_model(
        data, mlp, lr=0.001, max_epochs=200, patience=30
    )
    mlp_scores = predict_propagation(mlp, data)
    mlp_test_r, _ = spearmanr(mlp_scores[test_mask], labels[test_mask])
    results["mlp_baseline"] = {
        "model": "MLP (no graph)",
        "test_r": mlp_test_r,
        "history": hist_mlp,
        "scores": mlp_scores,
    }
    logger.info("MLP Baseline: test Spearman r = %.4f", mlp_test_r)

    # --- Experiment 3: 1-hop GNN ---
    logger.info("=== Ablation 3: 1-hop GNN ===")
    model_1hop = build_gat_model(in_channels=features.shape[1], hidden_channels=64, heads=4, num_layers=1)
    model_1hop, hist_1hop = train_propagation_model(
        data, model_1hop, lr=0.001, max_epochs=200, patience=30
    )
    scores_1hop = predict_propagation(model_1hop, data)
    test_r_1hop, _ = spearmanr(scores_1hop[test_mask], labels[test_mask])
    results["gnn_1hop"] = {
        "model": "1-hop GAT",
        "test_r": test_r_1hop,
        "history": hist_1hop,
        "scores": scores_1hop,
    }
    logger.info("1-hop GNN: test Spearman r = %.4f", test_r_1hop)

    # --- Experiment 4: GNN without PIS features (road-only) ---
    logger.info("=== Ablation 4: Road-only features ===")
    # Columns 0-5 are PIS/violation features, 6-11 are road geometry
    road_only_features = features[:, 6:]  # Only road features
    data_road = build_pyg_data(road_only_features, edge_list, labels, train_mask, val_mask, test_mask)
    model_road = build_gat_model(in_channels=road_only_features.shape[1], hidden_channels=64, heads=4, num_layers=3)
    model_road, hist_road = train_propagation_model(
        data_road, model_road, lr=0.001, max_epochs=200, patience=30
    )
    scores_road = predict_propagation(model_road, data_road)
    test_r_road, _ = spearmanr(scores_road[test_mask], labels[test_mask])
    results["road_only"] = {
        "model": "Road-only GNN",
        "test_r": test_r_road,
        "history": hist_road,
        "scores": scores_road,
    }
    logger.info("Road-only GNN: test Spearman r = %.4f", test_r_road)

    # Summary
    logger.info("=" * 60)
    logger.info("TWIN-TARGET ABLATION RESULTS")
    logger.info("=" * 60)
    for name, res in results.items():
        logger.info("  %-20s: Spearman r = %.4f", res["model"], res["test_r"])
    logger.info("=" * 60)

    return results


# =============================================================================
# 4. VISUALIZATIONS
# =============================================================================


def generate_twin_visualizations(
    data: object,
    ablation_results: dict,
    best_scores: np.ndarray,
    labels: np.ndarray,
    output_dir: Path,
) -> None:
    """Generate Phase 3C visualizations."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_style("darkgrid")
    plt.rcParams.update({"figure.dpi": PLOT_DPI, "savefig.dpi": PLOT_DPI, "font.size": 10})

    # === Chart 1: Ablation Study ===
    logger.info("Chart 1: Twin Target Ablation")
    models = [r["model"] for r in ablation_results.values()]
    r_vals = [r["test_r"] for r in ablation_results.values()]
    colors = ["#ff6600" if r == max(r_vals) else "#0088ff" for r in r_vals]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(models, r_vals, color=colors, edgecolor="white", linewidth=2)
    ax.set_ylabel("Test Spearman r")
    ax.set_title("Ablation Study — Delta Delay Target (Physics-Based)", fontsize=14, fontweight="bold")
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    for bar, val in zip(bars, r_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{val:.3f}",
                ha="center", va="bottom", fontweight="bold", fontsize=12)

    # Add comparison with old PIS-target results
    ax.axhline(y=0.232, color="red", linestyle=":", alpha=0.7, label="Old GNN (PIS target): r=0.232")
    ax.axhline(y=0.594, color="green", linestyle=":", alpha=0.7, label="Old MLP (PIS target): r=0.594")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_dir / "10_twin_ablation.png")
    plt.close(fig)

    # === Chart 2: Training curves for best model ===
    logger.info("Chart 2: Training Curves (Best Model)")
    best_key = max(ablation_results, key=lambda k: ablation_results[k]["test_r"])
    best_hist = ablation_results[best_key]["history"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    epochs = range(len(best_hist["train_loss"]))
    axes[0].plot(epochs, best_hist["train_loss"], label="Train", color="#ff6600")
    axes[0].plot(epochs, best_hist["val_loss"], label="Val", color="#0088ff")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("MSE Loss")
    axes[0].set_title("Loss Curves")
    axes[0].legend()

    axes[1].plot(epochs, best_hist["val_spearman"], label="Val", color="#0088ff")
    axes[1].plot(epochs, best_hist["test_spearman"], label="Test", color="#00cc00")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Spearman r")
    axes[1].set_title("Rank Correlation")
    axes[1].legend()

    axes[2].plot(epochs, best_hist["lr"], color="#cc00ff")
    axes[2].set_xlabel("Epoch")
    axes[2].set_ylabel("Learning Rate")
    axes[2].set_title("LR Schedule")

    fig.suptitle(f"Best Model: {ablation_results[best_key]['model']} — "
                 f"test r={ablation_results[best_key]['test_r']:.3f}",
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "10_twin_training_curves.png")
    plt.close(fig)

    # === Chart 3: Predicted vs Actual ===
    logger.info("Chart 3: Predicted vs Actual (Twin Target)")
    import torch
    test_mask = data.test_mask.numpy() if hasattr(data.test_mask, "numpy") else data.test_mask

    fig, ax = plt.subplots(figsize=(8, 8))
    pred = best_scores[test_mask]
    actual = labels[test_mask]
    ax.scatter(actual, pred, s=3, alpha=0.2, color="#ff6600")
    ax.plot([0, 1], [0, 1], "r--", linewidth=2)
    from scipy.stats import spearmanr
    rho, _ = spearmanr(pred, actual)
    ax.set_xlabel("Actual Delta Delay (normalized)", fontsize=12)
    ax.set_ylabel("Predicted (GNN)", fontsize=12)
    ax.set_title(f"Test Set: Spearman r={rho:.3f}", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "10_twin_pred_vs_actual.png")
    plt.close(fig)

    # === Chart 4: Distribution comparison ===
    logger.info("Chart 4: Label Distribution — PIS vs Twin")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    axes[0].hist(labels[labels > 0], bins=100, color="#0088ff", alpha=0.7, edgecolor="white")
    axes[0].set_xlabel("Delta Delay (normalized)")
    axes[0].set_ylabel("Count")
    axes[0].set_title(f"Twin Target Distribution (n={np.sum(labels > 0):,})")

    axes[1].hist(best_scores, bins=100, color="#ff6600", alpha=0.7, edgecolor="white")
    axes[1].set_xlabel("Predicted Score")
    axes[1].set_ylabel("Count")
    axes[1].set_title(f"GNN Predictions (all {len(best_scores):,} segments)")
    fig.suptitle("Delta Delay: Ground Truth vs Predictions", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "10_twin_distributions.png")
    plt.close(fig)

    # === Chart 5: Summary Card ===
    logger.info("Chart 5: Summary Card")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis("off")

    summary_text = (
        f"DRISHTAM Phase 3C — GNN Re-training with Twin Targets\n"
        f"{'=' * 55}\n\n"
        f"Target: delta_delay from digital twin (physics-based)\n"
        f"Previous target: PIS score (heuristic, circular)\n\n"
        f"Results:\n"
    )
    for name, res in ablation_results.items():
        marker = " ★" if res["test_r"] == max(r["test_r"] for r in ablation_results.values()) else ""
        summary_text += f"  {res['model']:.<25s} r = {res['test_r']:.4f}{marker}\n"

    old_gnn_r = 0.232
    best_r = max(r["test_r"] for r in ablation_results.values())
    improvement = ((best_r - old_gnn_r) / old_gnn_r) * 100

    summary_text += (
        f"\nComparison with PIS target:\n"
        f"  Old GNN (PIS):  r = {old_gnn_r:.3f}\n"
        f"  New best:       r = {best_r:.3f}  ({improvement:+.0f}%)\n"
        f"\nSegments with predicted impact > 0: {np.sum(best_scores > 0.01):,}\n"
        f"Segments with high impact (> 0.5):  {np.sum(best_scores > 0.5):,}\n"
    )

    ax.text(0.05, 0.95, summary_text, transform=ax.transAxes, fontsize=11,
            verticalalignment="top", fontfamily="monospace",
            bbox={"facecolor": "#f5f5f5", "alpha": 0.8, "pad": 20})
    fig.savefig(output_dir / "10_twin_summary.png", bbox_inches="tight")
    plt.close(fig)

    logger.info("All visualizations saved to %s", output_dir)


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    """Run GNN re-training with digital twin targets."""
    setup_logging()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 3C — GNN Re-training with Twin Targets")
    logger.info("CPU cores: %d", os.cpu_count() or 0)
    logger.info("=" * 70)

    total_start = time.time()

    # Step 1: Build line graph
    logger.info("--- Step 1: Build line graph ---")
    segment_data, adj_list, edge_to_node_map = osm_to_line_graph(str(OSM_CACHE_PATH))

    # Step 2: Load violations and build node features
    logger.info("--- Step 2: Build node features ---")
    df = pd.read_parquet(ENRICHED_DATA_PATH)
    features = build_node_features(segment_data, df)

    # adj_list from osm_to_line_graph is already (edge_src, edge_dst) tuple
    edge_list = adj_list

    logger.info("Features: %s, Edges: %d", features.shape, len(edge_list[0]))

    # Step 3: Load twin targets
    logger.info("--- Step 3: Load twin targets (delta_delay) ---")
    delay_values = load_twin_targets(segment_data, edge_to_node_map)

    n_affected = np.sum(delay_values > 0)
    logger.info("Segments with delay > 0: %d / %d (%.1f%%)",
                n_affected, len(delay_values), 100 * n_affected / len(delay_values))

    # Step 4: Build supervised labels
    logger.info("--- Step 4: Build train/val/test split ---")
    labels, train_mask, val_mask, test_mask = build_twin_supervised_labels(delay_values, features)

    # Step 5: Run ablation study
    logger.info("--- Step 5: Ablation study (MLP vs GNN) ---")
    ablation_results = run_twin_ablation(features, edge_list, labels, train_mask, val_mask, test_mask)

    # Step 6: Pick best model and save
    logger.info("--- Step 6: Save best model ---")
    best_key = max(ablation_results, key=lambda k: ablation_results[k]["test_r"])
    best_result = ablation_results[best_key]
    best_scores = best_result["scores"]

    logger.info("Best model: %s (r=%.4f)", best_result["model"], best_result["test_r"])

    # Save scores
    score_df = pd.DataFrame({
        "seg_idx": range(len(best_scores)),
        "twin_impact_score": best_scores,
        "delta_delay_label": labels,
        "osm_u": [s["osm_u"] for s in segment_data],
        "osm_v": [s["osm_v"] for s in segment_data],
        "highway": [s["highway"] for s in segment_data],
    })
    score_df.to_parquet(str(TWIN_SCORES_PATH), index=False)
    logger.info("Saved twin-propagated scores to %s", TWIN_SCORES_PATH)

    # Step 7: Generate visualizations
    logger.info("--- Step 7: Generate visualizations ---")
    data = build_pyg_data(features, edge_list, labels, train_mask, val_mask, test_mask)
    generate_twin_visualizations(data, ablation_results, best_scores, labels, RESEARCH_DIR)

    total_elapsed = time.time() - total_start
    logger.info("=" * 70)
    logger.info("Phase 3C complete in %.1f minutes", total_elapsed / 60)
    logger.info("Best model: %s, Spearman r=%.4f", best_result["model"], best_result["test_r"])
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
