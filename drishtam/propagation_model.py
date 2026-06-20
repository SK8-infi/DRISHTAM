"""DRISHTAM Graph Attention Network for congestion propagation.

3-layer GAT that learns how parking impact propagates through the
road network. Uses self-supervised training: mask known PIS values
and train the model to predict them from neighboring road features.

Key design: CPU multi-core training with PyTorch thread parallelism.
All matrix ops use all available cores via torch.set_num_threads().

Reference: plans/phase3_gnn_propagation.md
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Use all CPU cores for PyTorch operations
_NUM_CORES = os.cpu_count() or 4


_threads_configured = False


def _setup_torch_threads() -> None:
    """Configure PyTorch to use all available CPU cores (idempotent)."""
    global _threads_configured  # noqa: PLW0603
    import torch

    torch.set_num_threads(_NUM_CORES)
    if not _threads_configured:
        try:
            torch.set_num_interop_threads(min(_NUM_CORES, 4))
        except RuntimeError:
            pass  # Already set
        _threads_configured = True
    logger.info(
        "PyTorch threads: %d intra-op, %d inter-op (CPU cores: %d)",
        torch.get_num_threads(),
        torch.get_num_interop_threads(),
        _NUM_CORES,
    )


# =============================================================================
# 1. GAT MODEL
# =============================================================================


def build_gat_model(
    in_channels: int = 12,
    hidden_channels: int = 32,
    heads: int = 4,
    num_layers: int = 3,
    dropout: float = 0.3,
) -> object:
    """Build the ParkImpactGAT model.

    Architecture:
        Input (12 features)
        → GATConv(12 → 32, 4 heads, concat) → 128-dim → ReLU + Dropout
        → GATConv(128 → 32, 4 heads, concat) → 128-dim → ReLU + Dropout
        → GATConv(128 → 16, 4 heads, mean) → 16-dim → ReLU
        → Linear(16 → 1) → Sigmoid → [0, 1]

    3 GAT layers = 3-hop propagation neighborhood.

    Args:
        in_channels: Input feature dimension.
        hidden_channels: Hidden layer dimension per head.
        heads: Number of attention heads.
        num_layers: Number of GAT layers.
        dropout: Dropout rate.

    Returns:
        ParkImpactGAT model instance.
    """
    import torch
    import torch.nn.functional as f_nn  # noqa: N812
    from torch import nn
    from torch_geometric.nn import GATConv

    class ParkImpactGAT(nn.Module):
        """Graph Attention Network for parking impact propagation."""

        def __init__(self) -> None:
            super().__init__()
            self.dropout = dropout

            # Layer 1: in_channels → hidden_channels * heads (concat)
            self.conv1 = GATConv(
                in_channels,
                hidden_channels,
                heads=heads,
                concat=True,
                dropout=dropout,
            )

            # Layer 2: hidden_channels * heads → hidden_channels * heads (concat)
            self.conv2 = GATConv(
                hidden_channels * heads,
                hidden_channels,
                heads=heads,
                concat=True,
                dropout=dropout,
            )

            # Layer 3: hidden_channels * heads → hidden_channels/2 (mean, no concat)
            self.conv3 = GATConv(
                hidden_channels * heads,
                hidden_channels // 2,
                heads=heads,
                concat=False,
                dropout=dropout,
            )

            # Output head
            self.out = nn.Linear(hidden_channels // 2, 1)

            # Store attention weights for explainability
            self._attention_weights = []

        def forward(self, x: Any, edge_index: Any, return_attention: bool = False) -> Any:
            """Forward pass.

            Args:
                x: Node features (N, 12).
                edge_index: Edge index (2, E).
                return_attention: If True, store attention weights.

            Returns:
                Predicted propagated impact scores (N,).
            """
            self._attention_weights = []

            # Layer 1
            if return_attention:
                x, attn1 = self.conv1(x, edge_index, return_attention_weights=True)
                self._attention_weights.append(attn1)
            else:
                x = self.conv1(x, edge_index)
            x = f_nn.elu(x)
            x = f_nn.dropout(x, p=self.dropout, training=self.training)

            # Layer 2
            if return_attention:
                x, attn2 = self.conv2(x, edge_index, return_attention_weights=True)
                self._attention_weights.append(attn2)
            else:
                x = self.conv2(x, edge_index)
            x = f_nn.elu(x)
            x = f_nn.dropout(x, p=self.dropout, training=self.training)

            # Layer 3
            if return_attention:
                x, attn3 = self.conv3(x, edge_index, return_attention_weights=True)
                self._attention_weights.append(attn3)
            else:
                x = self.conv3(x, edge_index)
            x = f_nn.elu(x)

            # Output
            x = self.out(x).squeeze(-1)
            return torch.sigmoid(x)

        def get_attention_weights(self) -> list:
            """Return stored attention weights from last forward pass."""
            return self._attention_weights

    model = ParkImpactGAT()
    n_params = sum(p.numel() for p in model.parameters())
    logger.info("ParkImpactGAT: %d parameters", n_params)

    return model


# =============================================================================
# 2. TRAINING LOOP (Multi-Core)
# =============================================================================


def train_propagation_model(
    data: object,
    model: object = None,
    lr: float = 0.001,
    weight_decay: float = 5e-4,
    max_epochs: int = 300,
    patience: int = 30,
    lr_patience: int = 10,
    lr_factor: float = 0.5,
) -> tuple[object, dict]:
    """Train the GAT model with early stopping.

    Uses all CPU cores for matrix operations. Training loop:
    - Adam optimizer with weight decay
    - ReduceLROnPlateau scheduler
    - Early stopping on validation loss

    Args:
        data: PyG Data object with train/val/test masks.
        model: Optional pre-built model. If None, builds default.
        lr: Learning rate.
        weight_decay: L2 regularization.
        max_epochs: Maximum training epochs.
        patience: Early stopping patience.
        lr_patience: LR scheduler patience.
        lr_factor: LR reduction factor.

    Returns:
        Tuple of (trained model, training history dict).
    """
    import torch
    from scipy.stats import spearmanr

    _setup_torch_threads()

    if model is None:
        model = build_gat_model(in_channels=data.x.shape[1])

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=lr_patience, factor=lr_factor
    )
    criterion = torch.nn.MSELoss()

    history = {
        "train_loss": [],
        "val_loss": [],
        "val_spearman": [],
        "test_spearman": [],
        "lr": [],
    }

    best_val_loss = float("inf")
    best_model_state = None
    epochs_no_improve = 0

    logger.info("Training GAT: %d epochs max, patience=%d, lr=%.4f", max_epochs, patience, lr)
    start = time.time()

    for epoch in range(max_epochs):
        # --- Train ---
        model.train()
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        train_loss = criterion(out[data.train_mask], data.y[data.train_mask])
        train_loss.backward()
        optimizer.step()

        # --- Validate ---
        model.eval()
        with torch.no_grad():
            out = model(data.x, data.edge_index)
            val_loss = criterion(out[data.val_mask], data.y[data.val_mask]).item()

            # Spearman correlation on validation set
            val_pred = out[data.val_mask].numpy()
            val_true = data.y[data.val_mask].numpy()
            val_rho, _ = spearmanr(val_pred, val_true)

            # Test correlation (for monitoring, not for early stopping)
            test_pred = out[data.test_mask].numpy()
            test_true = data.y[data.test_mask].numpy()
            test_rho, _ = spearmanr(test_pred, test_true)

        scheduler.step(val_loss)
        current_lr = optimizer.param_groups[0]["lr"]

        history["train_loss"].append(train_loss.item())
        history["val_loss"].append(val_loss)
        history["val_spearman"].append(float(val_rho))
        history["test_spearman"].append(float(test_rho))
        history["lr"].append(current_lr)

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = {k: v.clone() for k, v in model.state_dict().items()}
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1

        if epoch % 20 == 0 or epochs_no_improve == 0:
            logger.info(
                "Epoch %3d: train=%.5f val=%.5f val_r=%.3f test_r=%.3f lr=%.6f %s",
                epoch,
                train_loss.item(),
                val_loss,
                val_rho,
                test_rho,
                current_lr,
                "★" if epochs_no_improve == 0 else "",
            )

        if epochs_no_improve >= patience:
            logger.info("Early stopping at epoch %d (patience=%d)", epoch, patience)
            break

    elapsed = time.time() - start
    logger.info("Training complete in %.1fs (%d epochs)", elapsed, epoch + 1)

    # Restore best model
    if best_model_state:
        model.load_state_dict(best_model_state)
        logger.info("Restored best model (val_loss=%.5f)", best_val_loss)

    # Final metrics
    model.eval()
    with torch.no_grad():
        out = model(data.x, data.edge_index)
        final_val_rho, _ = spearmanr(out[data.val_mask].numpy(), data.y[data.val_mask].numpy())
        final_test_rho, _ = spearmanr(out[data.test_mask].numpy(), data.y[data.test_mask].numpy())

    history["final_val_spearman"] = float(final_val_rho)
    history["final_test_spearman"] = float(final_test_rho)
    history["total_epochs"] = epoch + 1
    history["elapsed_seconds"] = elapsed

    logger.info(
        "Final: val Spearman=%.3f, test Spearman=%.3f",
        final_val_rho,
        final_test_rho,
    )

    return model, history


# =============================================================================
# 3. INFERENCE
# =============================================================================


def predict_propagation(model: object, data: object) -> np.ndarray:
    """Run full-city propagation inference.

    Every road segment gets a propagated impact score [0, 1], including
    segments with zero violations (they inherit impact from neighbors).

    Args:
        model: Trained ParkImpactGAT.
        data: PyG Data object.

    Returns:
        Array of propagated impact scores (N,).
    """
    import torch

    _setup_torch_threads()

    model.eval()
    with torch.no_grad():
        scores = model(data.x, data.edge_index).numpy()

    n_total = len(scores)
    n_nonzero = (scores > 0.01).sum()
    zero_viol_elevated = ((data.y.numpy() == 0) & (scores > np.median(scores[data.y.numpy() > 0]))).sum()

    logger.info(
        "Propagation: %d segments scored, %d with score > 0.01, %d zero-violation segments elevated",
        n_total,
        n_nonzero,
        zero_viol_elevated,
    )

    return scores


# =============================================================================
# 4. ABLATION STUDY (Multi-Core)
# =============================================================================


def run_ablation_study(data: object) -> dict[str, dict]:
    """Run ablation experiments to validate GNN contribution.

    Compares:
    1. Full GNN (all features, 3 layers)
    2. PIS-only features (cols 5-9)
    3. Road-only features (cols 0-4, 10-11)
    4. MLP baseline (same features, no graph)
    5. 1-hop GNN vs 2-hop vs 3-hop

    All experiments use all CPU cores.

    Args:
        data: PyG Data object.

    Returns:
        Dict with ablation results.
    """
    import torch

    _setup_torch_threads()

    results = {}

    # --- Experiment 1: Full model (baseline) ---
    logger.info("Ablation 1/5: Full GNN (3 layers, all features)")
    model_full, hist_full = train_propagation_model(data, max_epochs=150, patience=20)
    results["full_gnn_3hop"] = {
        "val_spearman": hist_full["final_val_spearman"],
        "test_spearman": hist_full["final_test_spearman"],
        "epochs": hist_full["total_epochs"],
    }

    # --- Experiment 2: PIS-only features ---
    logger.info("Ablation 2/5: PIS-only features")
    data_pis = data.clone()
    data_pis.x = data.x[:, 5:10]  # violation_count, mean_pis, max_pis, total_pis, capacity
    model_pis = build_gat_model(in_channels=5)
    _, hist_pis = train_propagation_model(data_pis, model=model_pis, max_epochs=150, patience=20)
    results["pis_only"] = {
        "val_spearman": hist_pis["final_val_spearman"],
        "test_spearman": hist_pis["final_test_spearman"],
        "epochs": hist_pis["total_epochs"],
    }

    # --- Experiment 3: Road-only features ---
    logger.info("Ablation 3/5: Road-only features")
    data_road = data.clone()
    road_cols = [0, 1, 2, 3, 4, 10, 11]
    data_road.x = data.x[:, road_cols]
    model_road = build_gat_model(in_channels=7)
    _, hist_road = train_propagation_model(data_road, model=model_road, max_epochs=150, patience=20)
    results["road_only"] = {
        "val_spearman": hist_road["final_val_spearman"],
        "test_spearman": hist_road["final_test_spearman"],
        "epochs": hist_road["total_epochs"],
    }

    # --- Experiment 4: MLP baseline (no graph structure) ---
    logger.info("Ablation 4/5: MLP baseline (no graph)")

    class MLPBaseline(torch.nn.Module):
        def __init__(self, in_dim: int) -> None:
            super().__init__()
            self.net = torch.nn.Sequential(
                torch.nn.Linear(in_dim, 64),
                torch.nn.ELU(),
                torch.nn.Dropout(0.3),
                torch.nn.Linear(64, 32),
                torch.nn.ELU(),
                torch.nn.Linear(32, 1),
                torch.nn.Sigmoid(),
            )

        def forward(self, x: Any, edge_index: Any, **_kwargs: Any) -> Any:
            return self.net(x).squeeze(-1)

    mlp = MLPBaseline(data.x.shape[1])
    _, hist_mlp = train_propagation_model(data, model=mlp, max_epochs=150, patience=20)
    results["mlp_baseline"] = {
        "val_spearman": hist_mlp["final_val_spearman"],
        "test_spearman": hist_mlp["final_test_spearman"],
        "epochs": hist_mlp["total_epochs"],
    }

    # --- Experiment 5: 1-hop GNN ---
    logger.info("Ablation 5/5: 1-hop GNN")

    class GATOneHop(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            from torch_geometric.nn import GATConv

            self.conv = GATConv(12, 16, heads=4, concat=False, dropout=0.3)
            self.out = torch.nn.Linear(16, 1)

        def forward(self, x: Any, edge_index: Any, **_kwargs: Any) -> Any:
            x = torch.nn.functional.elu(self.conv(x, edge_index))
            return torch.sigmoid(self.out(x).squeeze(-1))

    gat1 = GATOneHop()
    _, hist_1hop = train_propagation_model(data, model=gat1, max_epochs=150, patience=20)
    results["gnn_1hop"] = {
        "val_spearman": hist_1hop["final_val_spearman"],
        "test_spearman": hist_1hop["final_test_spearman"],
        "epochs": hist_1hop["total_epochs"],
    }

    # Summary
    logger.info("=== ABLATION SUMMARY ===")
    for name, res in sorted(results.items(), key=lambda x: x[1]["test_spearman"], reverse=True):
        logger.info(
            "  %-20s val_r=%.3f test_r=%.3f (%d epochs)",
            name,
            res["val_spearman"],
            res["test_spearman"],
            res["epochs"],
        )

    return results
