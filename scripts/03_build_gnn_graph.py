"""Phase 3: Build GNN graph + train GAT + propagation inference.

Usage:
    python scripts/03_build_gnn_graph.py

Runs on all CPU cores (torch.set_num_threads + joblib for graph ops).
Designed for e2-highmem-8 (64GB RAM, 8 vCPUs).

Steps:
    1. Load OSM graph → line graph transformation
    2. Load violations → aggregate per segment → 12D node features
    3. Self-supervised labels (PIS inpainting)
    4. Build PyG Data object
    5. Train GAT model (3 layers × 4 heads, early stopping)
    6. Ablation study (5 experiments)
    7. Full-city propagation inference
    8. Save model + scores
    9. Generate 10+ visualizations
    10. Save research report

Reference: plans/phase3_gnn_propagation.md
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
    PROPAGATED_SCORES_PATH,
    RESEARCH_DIR,
    setup_logging,
)
from drishtam.graph_builder import (
    build_node_features,
    build_pyg_data,
    build_self_supervised_labels,
    osm_to_line_graph,
)
from drishtam.propagation_model import (
    predict_propagation,
    run_ablation_study,
    train_propagation_model,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VISUALIZATIONS (10+ charts)
# =============================================================================


def generate_gnn_visualizations(
    data: object,
    scores: np.ndarray,
    segment_data: list[dict],
    history: dict,
    ablation_results: dict,
    output_dir: Path,
) -> None:
    """Generate all Phase 3 visualizations."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_style("darkgrid")
    plt.rcParams.update({"figure.dpi": PLOT_DPI, "savefig.dpi": PLOT_DPI, "font.size": 10})

    labels = data.y.numpy()

    # === Chart 1: Training Curves ===
    logger.info("Chart 1: Training Curves")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    epochs = range(len(history["train_loss"]))
    axes[0].plot(epochs, history["train_loss"], label="Train", color="#ff6600")
    axes[0].plot(epochs, history["val_loss"], label="Val", color="#0088ff")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("MSE Loss")
    axes[0].set_title("Loss Curves")
    axes[0].legend()

    axes[1].plot(epochs, history["val_spearman"], label="Val", color="#0088ff")
    axes[1].plot(epochs, history["test_spearman"], label="Test", color="#00cc00")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Spearman r")
    axes[1].set_title("Rank Correlation")
    axes[1].legend()

    axes[2].plot(epochs, history["lr"], color="#cc00ff")
    axes[2].set_xlabel("Epoch")
    axes[2].set_ylabel("Learning Rate")
    axes[2].set_title("LR Schedule")

    fig.suptitle(
        f"GAT Training — {history['total_epochs']} epochs, "
        f"val r={history['final_val_spearman']:.3f}, "
        f"test r={history['final_test_spearman']:.3f}",
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(output_dir / "08_training_curves.png")
    plt.close(fig)

    # === Chart 2: Predicted vs Actual ===
    logger.info("Chart 2: Predicted vs Actual")
    test_mask = data.test_mask.numpy()
    val_mask = data.val_mask.numpy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, mask, name in [(axes[0], val_mask, "Validation"), (axes[1], test_mask, "Test")]:
        pred = scores[mask]
        actual = labels[mask]
        ax.scatter(actual, pred, s=2, alpha=0.3, color="#ff6600")
        ax.plot([0, 1], [0, 1], "r--", linewidth=1)
        from scipy.stats import spearmanr

        rho, _ = spearmanr(pred, actual)
        ax.set_xlabel("Actual PIS (normalized)")
        ax.set_ylabel("Predicted (propagated)")
        ax.set_title(f"{name} Set (Spearman r={rho:.3f})")
    fig.suptitle("GAT Prediction Quality — Self-Supervised PIS Inpainting", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "08_pred_vs_actual.png")
    plt.close(fig)

    # === Chart 3: Propagated Impact Distribution ===
    logger.info("Chart 3: Propagated Impact Distribution")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].hist(labels[labels > 0], bins=80, color="#0088ff", alpha=0.7, label="Direct PIS")
    axes[0].hist(scores[labels > 0], bins=80, color="#ff6600", alpha=0.5, label="Propagated")
    axes[0].set_xlabel("Impact Score (0-1)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Segments WITH Violations")
    axes[0].legend()

    axes[1].hist(scores[labels == 0], bins=80, color="#cc00ff", alpha=0.7)
    axes[1].set_xlabel("Propagated Impact Score")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Segments WITHOUT Violations (Network Effect!)")
    fig.suptitle("Direct PIS vs Propagated Impact", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "08_propagated_distribution.png")
    plt.close(fig)

    # === Chart 4: Before vs After Propagation (Spatial) ===
    logger.info("Chart 4: Before vs After Propagation Map")
    # Get segment centroids (approximate from OSM node positions)
    seg_lats = []
    seg_lons = []
    for seg in segment_data:
        # Use segment index as a proxy; actual lat/lon would need OSM node coords
        # We'll use the node features (junction degrees) as spatial proxy
        seg_lats.append(seg.get("_lat", 0))
        seg_lons.append(seg.get("_lon", 0))

    if any(lat != 0 for lat in seg_lats):
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        # Left: Direct PIS (only violation segments)
        has_viol = labels > 0
        sample_idx = np.random.default_rng(42).choice(
            np.where(has_viol)[0], size=min(30000, has_viol.sum()), replace=False
        )
        axes[0].scatter(
            [seg_lons[i] for i in sample_idx],
            [seg_lats[i] for i in sample_idx],
            c=labels[sample_idx],
            cmap="YlOrRd",
            s=1,
            alpha=0.5,
            vmin=0,
            vmax=0.7,
        )
        axes[0].set_title("Direct PIS (where violations ARE)")

        # Right: Propagated (all segments)
        all_idx = np.random.default_rng(42).choice(len(scores), size=min(50000, len(scores)), replace=False)
        sc = axes[1].scatter(
            [seg_lons[i] for i in all_idx],
            [seg_lats[i] for i in all_idx],
            c=scores[all_idx],
            cmap="YlOrRd",
            s=1,
            alpha=0.5,
            vmin=0,
            vmax=0.7,
        )
        axes[1].set_title("Propagated Impact (where violations HURT)")
        plt.colorbar(sc, ax=axes[1], shrink=0.8)

        fig.suptitle("Before vs After GNN Propagation", fontsize=16, fontweight="bold")
        fig.tight_layout()
        fig.savefig(output_dir / "08_before_after_propagation.png")
        plt.close(fig)

    # === Chart 5: Hidden Victims ===
    logger.info("Chart 5: Hidden Victims Analysis")
    zero_viol = labels == 0
    median_prop = np.median(scores[labels > 0])
    hidden_victims = zero_viol & (scores > median_prop)
    n_hidden = hidden_victims.sum()

    fig, ax = plt.subplots(figsize=(12, 6))
    bins = np.linspace(0, 1, 50)
    ax.hist(
        scores[zero_viol & ~hidden_victims], bins=bins, color="#cccccc", alpha=0.7, label="Low-impact (no violations)"
    )
    ax.hist(scores[hidden_victims], bins=bins, color="#ff0000", alpha=0.7, label=f"Hidden victims ({n_hidden})")
    ax.axvline(
        median_prop, color="blue", linestyle="--", label=f"Median propagated (violation segs) = {median_prop:.3f}"
    )
    ax.set_xlabel("Propagated Impact Score")
    ax.set_ylabel("Count")
    ax.set_title(
        f"Hidden Victims — {n_hidden} Zero-Violation Segments with High Propagated Impact",
        fontsize=13,
        fontweight="bold",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "08_hidden_victims.png")
    plt.close(fig)

    # === Chart 6: Ablation Study ===
    logger.info("Chart 6: Ablation Study")
    if ablation_results:
        names = list(ablation_results.keys())
        val_rs = [ablation_results[n]["val_spearman"] for n in names]
        test_rs = [ablation_results[n]["test_spearman"] for n in names]

        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(names))
        w = 0.35
        ax.bar(x - w / 2, val_rs, w, label="Val Spearman r", color="#0088ff", edgecolor="white")
        ax.bar(x + w / 2, test_rs, w, label="Test Spearman r", color="#ff6600", edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=9)
        ax.set_ylabel("Spearman r")
        ax.set_title("Ablation Study — Does the Graph Structure Help?", fontsize=14, fontweight="bold")
        ax.legend()
        for i, (v, t) in enumerate(zip(val_rs, test_rs, strict=True)):
            ax.text(i - w / 2, v + 0.01, f"{v:.3f}", ha="center", fontsize=8)
            ax.text(i + w / 2, t + 0.01, f"{t:.3f}", ha="center", fontsize=8)
        fig.tight_layout()
        fig.savefig(output_dir / "08_ablation_study.png")
        plt.close(fig)

    # === Chart 7: Node Feature Importance ===
    logger.info("Chart 7: Feature Distributions")
    feature_names = [
        "lanes",
        "width",
        "road_tier",
        "length",
        "is_link",
        "viol_count",
        "mean_pis",
        "max_pis",
        "total_pis",
        "cap_blocked",
        "junc_deg_start",
        "junc_deg_end",
    ]
    fig, axes = plt.subplots(3, 4, figsize=(20, 12))
    for i, (ax, name) in enumerate(zip(axes.flat, feature_names, strict=True)):
        vals = data.x[:, i].numpy()
        ax.hist(vals, bins=50, color="#0088ff", alpha=0.7, edgecolor="white")
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("")
    fig.suptitle("Node Feature Distributions (12D)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "08_feature_distributions.png")
    plt.close(fig)

    # === Chart 8: Degree Distribution ===
    logger.info("Chart 8: Degree Distribution")
    edge_index = data.edge_index.numpy()
    degrees = np.bincount(edge_index[0], minlength=data.num_nodes)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(degrees, bins=100, color="#00cc66", edgecolor="white", alpha=0.8)
    ax.set_xlabel("Node Degree")
    ax.set_ylabel("Count")
    ax.set_title(
        f"Line Graph Degree Distribution — mean={degrees.mean():.1f}, max={degrees.max()}",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(output_dir / "08_degree_distribution.png")
    plt.close(fig)

    # === Chart 9: Propagation by Road Type ===
    logger.info("Chart 9: Propagation by Road Type")
    road_tiers = [seg["highway"] for seg in segment_data]
    tier_set = sorted(set(road_tiers))
    tier_mean_direct = []
    tier_mean_propagated = []
    tier_labels = []
    for tier in tier_set:
        mask = np.array([t == tier for t in road_tiers])
        if mask.sum() > 100:
            tier_mean_direct.append(labels[mask].mean())
            tier_mean_propagated.append(scores[mask].mean())
            tier_labels.append(tier)

    if tier_labels:
        fig, ax = plt.subplots(figsize=(14, 6))
        x = np.arange(len(tier_labels))
        w = 0.35
        ax.bar(x - w / 2, tier_mean_direct, w, label="Direct PIS", color="#0088ff")
        ax.bar(x + w / 2, tier_mean_propagated, w, label="Propagated", color="#ff6600")
        ax.set_xticks(x)
        ax.set_xticklabels(tier_labels, rotation=45)
        ax.set_ylabel("Mean Score")
        ax.set_title("Direct PIS vs Propagated Impact by Road Type", fontsize=14, fontweight="bold")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "08_propagation_by_road_type.png")
        plt.close(fig)

    # === Chart 10: Graph Summary ===
    logger.info("Chart 10: Graph Summary Card")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")
    summary_text = (
        f"DRISHTAM — GNN Propagation Summary\n"
        f"{'=' * 50}\n\n"
        f"Graph:  {data.num_nodes:,} nodes × {data.num_edges:,} edges\n"
        f"Degree: mean={degrees.mean():.1f}, max={degrees.max()}\n"
        f"Features: {data.num_node_features} per node\n\n"
        f"Training: {history['total_epochs']} epochs in {history['elapsed_seconds']:.0f}s\n"
        f"Val Spearman r:  {history['final_val_spearman']:.3f}\n"
        f"Test Spearman r: {history['final_test_spearman']:.3f}\n\n"
        f"Propagation:\n"
        f"  Segments with violations: {(labels > 0).sum():,}\n"
        f"  Segments w/o violations:  {(labels == 0).sum():,}\n"
        f"  Hidden victims:           {n_hidden:,}\n"
        f"  Mean direct PIS:          {labels[labels > 0].mean():.3f}\n"
        f"  Mean propagated:          {scores.mean():.3f}\n"
    )
    ax.text(
        0.1, 0.9, summary_text, transform=ax.transAxes, fontsize=12, verticalalignment="top", fontfamily="monospace"
    )
    fig.savefig(output_dir / "08_graph_summary.png")
    plt.close(fig)

    logger.info("All %d visualizations saved to %s", 10, output_dir)


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    """Run Phase 3 pipeline end-to-end."""
    setup_logging()
    logger.info("=" * 70)
    logger.info("DRISHTAM Phase 3 — GNN Congestion Propagation")
    logger.info("CPU cores: %d", os.cpu_count() or 0)
    logger.info("=" * 70)

    total_start = time.time()
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Build line graph
    logger.info("--- Step 1: Line graph construction ---")
    segment_data, edge_list, node_to_segs = osm_to_line_graph(OSM_CACHE_PATH)

    # Step 2: Load violations + build node features
    logger.info("--- Step 2: Node feature engineering ---")
    df = pd.read_parquet(ENRICHED_DATA_PATH)
    logger.info("Loaded violations: %d × %d", len(df), len(df.columns))
    features = build_node_features(segment_data, df)

    # Step 3: Self-supervised labels
    logger.info("--- Step 3: Self-supervised labels (PIS inpainting) ---")
    labels, train_mask, val_mask, test_mask = build_self_supervised_labels(features)

    # Step 4: Build PyG Data
    logger.info("--- Step 4: Building PyG Data object ---")
    data = build_pyg_data(features, edge_list, labels, train_mask, val_mask, test_mask)

    # Save graph data
    import torch

    torch.save(data, str(GRAPH_DATA_PATH))
    logger.info("Graph saved to %s", GRAPH_DATA_PATH)

    # Step 5: Train GAT
    logger.info("--- Step 5: Training GAT model ---")
    model, history = train_propagation_model(data, max_epochs=300, patience=30)

    # Save model
    model_path = MODELS_DIR / "gat_propagation.pt"
    torch.save(model.state_dict(), str(model_path))
    logger.info("Model saved to %s", model_path)

    # Step 6: Ablation study
    logger.info("--- Step 6: Ablation study ---")
    ablation_results = run_ablation_study(data)

    # Step 7: Full-city propagation
    logger.info("--- Step 7: Full-city propagation inference ---")
    scores = predict_propagation(model, data)

    # Step 8: Save propagated scores
    logger.info("--- Step 8: Saving propagated scores ---")
    prop_df = pd.DataFrame(
        {
            "seg_idx": range(len(scores)),
            "propagated_impact": scores,
            "direct_pis": labels,
            "has_violations": labels > 0,
            "highway": [seg["highway"] for seg in segment_data],
            "road_name": [seg.get("name", "Unknown") for seg in segment_data],
            "lanes": [seg["lanes"] for seg in segment_data],
            "width": [seg["width"] for seg in segment_data],
            "length": [seg["length"] for seg in segment_data],
        }
    )
    prop_df.to_parquet(PROPAGATED_SCORES_PATH, index=False, engine="pyarrow")
    logger.info(
        "Saved: %s (%d segments, %.1f MB)",
        PROPAGATED_SCORES_PATH,
        len(prop_df),
        PROPAGATED_SCORES_PATH.stat().st_size / 1e6,
    )

    # Step 9: Visualizations
    logger.info("--- Step 9: Generating visualizations ---")
    generate_gnn_visualizations(data, scores, segment_data, history, ablation_results, RESEARCH_DIR)

    # Step 10: Summary
    total_elapsed = time.time() - total_start
    logger.info("=" * 70)
    logger.info("PHASE 3 COMPLETE in %.1fs", total_elapsed)
    logger.info("Graph: %d nodes, %d edges", data.num_nodes, data.num_edges)
    logger.info("GAT: val r=%.3f, test r=%.3f", history["final_val_spearman"], history["final_test_spearman"])
    logger.info(
        "Hidden victims: %d zero-violation segments with elevated impact",
        (scores[labels == 0] > np.median(scores[labels > 0])).sum(),
    )
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
