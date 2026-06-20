# %% [markdown]
# # DRISHTAM Phase 3C — GNN Retraining with Digital Twin Targets (GPU)
#
# **Purpose**: Train the ParkImpactGAT model on GPU (Colab T4/L4) using
# physics-based targets from the v6 digital twin simulation.
#
# **Data files needed** (upload to Colab or mount Drive):
# - `bengaluru_roads.graphml` — OSM road network
# - `violations_enriched.parquet` — enriched violation data
# - `delay_metrics.parquet` — v6 simulation delta-delay targets
#
# **Expected speedup**: ~10-20× vs 8-core CPU (8 min/epoch → ~30 sec/epoch)

# %% [markdown]
# ## 0. Setup — Install Dependencies

# %%
# !pip install torch-geometric torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.4.0+cu121.html
# !pip install networkx osmnx pandas pyarrow scipy

# %%
import os
import time
import logging
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from scipy.stats import spearmanr

# GPU setup
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {device}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# %% [markdown]
# ## 1. Upload Data Files
#
# Run this cell and upload the 3 files when prompted.
# Or mount Google Drive if files are there.

# %%
# Option A: Upload files directly
# from google.colab import files
# uploaded = files.upload()  # Upload bengaluru_roads.graphml, violations_enriched.parquet, delay_metrics.parquet

# Option B: Mount Google Drive
# from google.colab import drive
# drive.mount('/content/drive')
# DATA_DIR = '/content/drive/MyDrive/drishtam_data'

# Option C: Local paths (if running locally with GPU)
DATA_DIR = os.environ.get('DRISHTAM_DATA', '.')
OSM_GRAPH_PATH = os.path.join(DATA_DIR, 'bengaluru_roads.graphml')
ENRICHED_DATA_PATH = os.path.join(DATA_DIR, 'violations_enriched.parquet')
DELAY_METRICS_PATH = os.path.join(DATA_DIR, 'delay_metrics.parquet')

# Verify files exist
for path in [OSM_GRAPH_PATH, ENRICHED_DATA_PATH, DELAY_METRICS_PATH]:
    if os.path.exists(path):
        sz = os.path.getsize(path) / 1e6
        print(f"  ✅ {os.path.basename(path)}: {sz:.1f} MB")
    else:
        print(f"  ❌ {os.path.basename(path)}: NOT FOUND — upload this file!")

# %% [markdown]
# ## 2. Build Line Graph from OSM

# %%
def build_line_graph(osm_path):
    """Convert OSM road graph to line graph (roads=nodes, junctions=edges)."""
    import networkx as nx

    logger.info("Loading OSM graph from %s", osm_path)
    G = nx.read_graphml(osm_path)
    logger.info("OSM graph loaded: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # Extract road segments
    segment_data = []
    for idx, (u, v, data) in enumerate(G.edges(data=True)):
        seg = {
            'seg_idx': idx,
            'osm_u': str(u),
            'osm_v': str(v),
            'length_m': float(data.get('length', 100)),
            'highway': data.get('highway', 'residential'),
            'lanes': int(data.get('lanes', 1)) if data.get('lanes') else 1,
            'maxspeed': float(data.get('maxspeed', 30)) if data.get('maxspeed') else 30.0,
            'name': data.get('name', ''),
            'oneway': data.get('oneway', 'False') == 'True',
        }
        segment_data.append(seg)

    n_segments = len(segment_data)
    logger.info("Extracted %d road segments (line graph nodes)", n_segments)

    # Build adjacency
    logger.info("Building line graph adjacency...")
    node_to_segments = {}
    for seg in segment_data:
        for node in [seg['osm_u'], seg['osm_v']]:
            if node not in node_to_segments:
                node_to_segments[node] = []
            node_to_segments[node].append(seg['seg_idx'])

    edge_src, edge_dst = [], []
    junction_degrees = {}
    for osm_node, seg_indices in node_to_segments.items():
        degree = len(seg_indices)
        junction_degrees[osm_node] = degree
        indices = seg_indices[:20] if degree > 20 else seg_indices
        for i, s1 in enumerate(indices):
            for s2 in indices[i + 1:]:
                edge_src.extend([s1, s2])
                edge_dst.extend([s2, s1])

    for seg in segment_data:
        seg['junction_degree_start'] = junction_degrees.get(seg['osm_u'], 1)
        seg['junction_degree_end'] = junction_degrees.get(seg['osm_v'], 1)

    logger.info("Line graph: %d nodes, %d edges (avg degree %.1f)",
                n_segments, len(edge_src) // 2, len(edge_src) / max(n_segments, 1))
    return segment_data, (edge_src, edge_dst), node_to_segments

# %%
t0 = time.time()
segment_data, edge_list, node_to_segments = build_line_graph(OSM_GRAPH_PATH)
print(f"Line graph built in {time.time()-t0:.1f}s")

# %% [markdown]
# ## 3. Build Node Features (12D)

# %%
def build_node_features(segment_data, df_violations):
    """Build 12D feature vector per road segment."""
    n_segments = len(segment_data)

    # Road hierarchy encoding
    highway_tiers = {
        'motorway': 5, 'trunk': 4, 'primary': 3, 'secondary': 2,
        'tertiary': 1, 'motorway_link': 4, 'trunk_link': 3,
        'primary_link': 2, 'secondary_link': 1, 'tertiary_link': 1,
    }

    # Per-segment violation aggregation
    logger.info("Aggregating violations per road segment...")
    seg_violations = {}
    seg_pis = {}

    # Create spatial index for matching violations to segments
    seg_coords = {}
    for seg in segment_data:
        seg_coords[seg['seg_idx']] = (seg['osm_u'], seg['osm_v'])

    # Match violations to segments via OSM node proximity
    if 'nearest_edge_u' in df_violations.columns and 'nearest_edge_v' in df_violations.columns:
        for _, row in df_violations.iterrows():
            u, v = str(row.get('nearest_edge_u', '')), str(row.get('nearest_edge_v', ''))
            for seg in segment_data:
                if (seg['osm_u'] == u and seg['osm_v'] == v) or \
                   (seg['osm_u'] == v and seg['osm_v'] == u):
                    idx = seg['seg_idx']
                    seg_violations[idx] = seg_violations.get(idx, 0) + 1
                    pis = row.get('parking_impact_score', row.get('pis', 0))
                    seg_pis[idx] = max(seg_pis.get(idx, 0), float(pis) if pd.notna(pis) else 0)
                    break

    n_matched = len(seg_violations)
    logger.info("Matched %d violations to %d segments (of %d total)",
                sum(seg_violations.values()), n_matched, n_segments)

    # Build feature matrix
    features = np.zeros((n_segments, 12), dtype=np.float32)
    for i, seg in enumerate(segment_data):
        hw = seg.get('highway', 'residential')
        if isinstance(hw, list): hw = hw[0]
        tier = highway_tiers.get(hw, 0)

        features[i, 0] = np.log1p(seg.get('length_m', 100))        # log length
        features[i, 1] = seg.get('lanes', 1)                         # lanes
        features[i, 2] = seg.get('maxspeed', 30) / 120.0             # speed (normalized)
        features[i, 3] = tier / 5.0                                   # road tier
        features[i, 4] = float(seg.get('oneway', False))             # oneway flag
        features[i, 5] = np.log1p(seg.get('junction_degree_start', 1))  # junction degree
        features[i, 6] = np.log1p(seg.get('junction_degree_end', 1))
        features[i, 7] = np.log1p(seg_violations.get(i, 0))         # violation count
        features[i, 8] = seg_pis.get(i, 0)                          # max PIS
        features[i, 9] = float(seg_violations.get(i, 0) > 0)        # has violations
        features[i, 10] = min(seg.get('lanes', 1), 1) * 0.184       # capacity blocked proxy
        features[i, 11] = features[i, 3] * features[i, 7]           # tier × violation interaction

    # Handle NaN
    features = np.nan_to_num(features, 0.0)
    logger.info("Node features: shape=%s, no NaN=%s", features.shape, not np.any(np.isnan(features)))
    return features

# %%
df = pd.read_parquet(ENRICHED_DATA_PATH)
features = build_node_features(segment_data, df)
print(f"Features: {features.shape}")
del df  # free memory

# %% [markdown]
# ## 4. Load Twin Targets (delta_delay from v6 simulation)

# %%
def load_twin_targets(delay_path, n_segments):
    """Load impact_score targets from simulation delay_metrics."""
    df_delay = pd.read_parquet(delay_path)
    logger.info("Loaded delay metrics: %d rows × %d cols", len(df_delay), len(df_delay.columns))
    logger.info("Columns: %s", list(df_delay.columns))

    target_col = 'impact_score'
    if target_col not in df_delay.columns:
        for col in ['delta_time_daily', 'delta_flow_daily']:
            if col in df_delay.columns:
                target_col = col
                break

    logger.info("Using target column: %s", target_col)
    raw_targets = df_delay[target_col].values

    # Positional mapping
    labels = np.zeros(n_segments, dtype=np.float32)
    n_map = min(len(raw_targets), n_segments)
    labels[:n_map] = raw_targets[:n_map]
    logger.info("Mapped %d / %d segments", n_map, n_segments)

    # Normalize: clip at p99, scale to [0, 1]
    positive_mask = labels > 0
    n_positive = positive_mask.sum()
    if n_positive > 0:
        p99 = np.percentile(labels[positive_mask], 99)
        logger.info("Positive segments: %d (%.1f%%), p99=%.4f",
                    n_positive, 100 * n_positive / n_segments, p99)
        labels = np.clip(labels, 0, p99) / max(p99, 1e-8)
    else:
        logger.warning("No positive delays found!")

    return labels

# %%
labels = load_twin_targets(DELAY_METRICS_PATH, len(segment_data))
print(f"Labels: {labels.shape}, range [{labels.min():.4f}, {labels.max():.4f}], "
      f"mean={labels.mean():.4f}, >0: {(labels > 0).sum()}")

# %% [markdown]
# ## 5. Build Train/Val/Test Split

# %%
def build_split(labels, train_ratio=0.6, val_ratio=0.2):
    """Stratified split: include both affected and unaffected segments."""
    n = len(labels)
    affected = np.where(labels > 0)[0]
    unaffected = np.where(labels == 0)[0]

    # Sample equal number of unaffected to balance
    n_sample = min(len(affected), len(unaffected))
    rng = np.random.RandomState(42)
    if len(unaffected) > n_sample:
        unaffected = rng.choice(unaffected, n_sample, replace=False)

    all_indices = np.concatenate([affected, unaffected])
    rng.shuffle(all_indices)

    n_total = len(all_indices)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)

    train_mask = np.zeros(n, dtype=bool)
    val_mask = np.zeros(n, dtype=bool)
    test_mask = np.zeros(n, dtype=bool)

    train_mask[all_indices[:n_train]] = True
    val_mask[all_indices[n_train:n_train + n_val]] = True
    test_mask[all_indices[n_train + n_val:]] = True

    logger.info("Split: %d train, %d val, %d test (of %d selected, %d total)",
                train_mask.sum(), val_mask.sum(), test_mask.sum(), n_total, n)
    return train_mask, val_mask, test_mask

# %%
train_mask, val_mask, test_mask = build_split(labels)

# %% [markdown]
# ## 6. Build PyG Data Object & Move to GPU

# %%
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

# Move to GPU!
data = data.to(device)
print(f"PyG Data on {device}: {data.num_nodes} nodes, {data.num_edges} edges, "
      f"{data.num_node_features} features")
if torch.cuda.is_available():
    print(f"GPU memory: {torch.cuda.memory_allocated()/1e9:.2f} GB allocated")

# %% [markdown]
# ## 7. Model Definition — ParkImpactGAT (GPU)

# %%
from torch_geometric.nn import GATConv

class ParkImpactGAT(nn.Module):
    """3-hop Graph Attention Network for parking impact propagation."""

    def __init__(self, in_channels=12, hidden=32, heads=4, dropout=0.3):
        super().__init__()
        self.dropout = dropout

        # Layer 1: in → hidden*heads (concat)
        self.conv1 = GATConv(in_channels, hidden, heads=heads, concat=True, dropout=dropout)
        # Layer 2: hidden*heads → hidden*heads (concat)
        self.conv2 = GATConv(hidden * heads, hidden, heads=heads, concat=True, dropout=dropout)
        # Layer 3: hidden*heads → hidden//2 (mean, no concat)
        self.conv3 = GATConv(hidden * heads, hidden // 2, heads=heads, concat=False, dropout=dropout)
        # Output
        self.out = nn.Linear(hidden // 2, 1)

    def forward(self, x, edge_index):
        x = F.elu(self.conv1(x, edge_index))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = F.elu(self.conv2(x, edge_index))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = F.elu(self.conv3(x, edge_index))
        x = self.out(x).squeeze(-1)
        return torch.sigmoid(x)

class SimpleMLPBaseline(nn.Module):
    """MLP baseline (no graph structure) for ablation comparison."""

    def __init__(self, in_channels=12, hidden=64, dropout=0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_channels, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),
            nn.Sigmoid(),
        )

    def forward(self, x, edge_index=None):
        return self.net(x).squeeze(-1)

class OneHopGAT(nn.Module):
    """1-hop GAT for ablation — does graph help vs more hops?"""

    def __init__(self, in_channels=12, hidden=32, heads=4, dropout=0.3):
        super().__init__()
        self.dropout = dropout
        self.conv1 = GATConv(in_channels, hidden, heads=heads, concat=False, dropout=dropout)
        self.out = nn.Linear(hidden, 1)

    def forward(self, x, edge_index):
        x = F.elu(self.conv1(x, edge_index))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.out(x).squeeze(-1)
        return torch.sigmoid(x)

# %% [markdown]
# ## 8. GPU Training Loop

# %%
def train_model(model, data, name="Model", max_epochs=200, patience=30,
                lr=0.001, weight_decay=5e-4):
    """Train a model on GPU with early stopping."""
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', patience=10, factor=0.5
    )
    criterion = nn.MSELoss()

    best_val_loss = float('inf')
    best_state = None
    no_improve = 0
    history = {'train_loss': [], 'val_loss': [], 'val_r': [], 'test_r': []}

    print(f"\n{'='*60}")
    print(f"Training {name}: {sum(p.numel() for p in model.parameters())} params")
    print(f"{'='*60}")
    start = time.time()

    for epoch in range(max_epochs):
        # Train
        model.train()
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        loss = criterion(out[data.train_mask], data.y[data.train_mask])
        loss.backward()
        optimizer.step()

        # Eval
        model.eval()
        with torch.no_grad():
            out = model(data.x, data.edge_index)
            val_loss = criterion(out[data.val_mask], data.y[data.val_mask]).item()

            # Spearman r (move to CPU for scipy)
            val_r, _ = spearmanr(out[data.val_mask].cpu().numpy(),
                                 data.y[data.val_mask].cpu().numpy())
            test_r, _ = spearmanr(out[data.test_mask].cpu().numpy(),
                                  data.y[data.test_mask].cpu().numpy())

        scheduler.step(val_loss)
        cur_lr = optimizer.param_groups[0]['lr']

        history['train_loss'].append(loss.item())
        history['val_loss'].append(val_loss)
        history['val_r'].append(float(val_r))
        history['test_r'].append(float(test_r))

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
            marker = '★'
        else:
            no_improve += 1
            marker = ''

        if epoch % 10 == 0 or no_improve == 0:
            elapsed = time.time() - start
            print(f"  Epoch {epoch:3d}: train={loss.item():.5f} val={val_loss:.5f} "
                  f"val_r={val_r:.3f} test_r={test_r:.3f} lr={cur_lr:.6f} "
                  f"[{elapsed:.0f}s] {marker}")

        if no_improve >= patience:
            print(f"  Early stopping at epoch {epoch}")
            break

    elapsed = time.time() - start
    print(f"  Training complete in {elapsed:.1f}s ({epoch+1} epochs)")

    # Restore best
    if best_state:
        model.load_state_dict(best_state)

    # Final metrics
    model.eval()
    with torch.no_grad():
        out = model(data.x, data.edge_index)
        final_val_r, _ = spearmanr(out[data.val_mask].cpu().numpy(),
                                    data.y[data.val_mask].cpu().numpy())
        final_test_r, _ = spearmanr(out[data.test_mask].cpu().numpy(),
                                     data.y[data.test_mask].cpu().numpy())

    print(f"\n  ▶ {name} FINAL: val_r={final_val_r:.4f}, test_r={final_test_r:.4f}")
    history['final_val_r'] = final_val_r
    history['final_test_r'] = final_test_r
    history['elapsed'] = elapsed
    return model, history

# %% [markdown]
# ## 9. Ablation Study — MLP vs 1-hop vs 3-hop GAT

# %%
results = {}

# Ablation 1: Full 3-hop GAT
gat_model = ParkImpactGAT(in_channels=data.num_node_features)
gat_model, gat_hist = train_model(gat_model, data, name="3-hop GAT", max_epochs=200)
results['3-hop GAT'] = gat_hist

# %%
# Ablation 2: MLP (no graph)
mlp_model = SimpleMLPBaseline(in_channels=data.num_node_features)
mlp_model, mlp_hist = train_model(mlp_model, data, name="MLP (no graph)", max_epochs=200)
results['MLP'] = mlp_hist

# %%
# Ablation 3: 1-hop GAT
one_hop = OneHopGAT(in_channels=data.num_node_features)
one_hop, one_hist = train_model(one_hop, data, name="1-hop GAT", max_epochs=200)
results['1-hop GAT'] = one_hist

# %% [markdown]
# ## 10. Results Comparison

# %%
print("\n" + "=" * 70)
print("ABLATION STUDY RESULTS — Twin-Supervised (v6 delay targets)")
print("=" * 70)
print(f"{'Model':<20} {'Val r':>10} {'Test r':>10} {'Time':>10}")
print("-" * 50)
for name, hist in sorted(results.items(), key=lambda x: -x[1].get('final_test_r', 0)):
    print(f"{name:<20} {hist['final_val_r']:>10.4f} {hist['final_test_r']:>10.4f} "
          f"{hist['elapsed']:>8.1f}s")
print("-" * 50)

# %% [markdown]
# ## 11. Training Curves

# %%
try:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Loss curves
    for name, hist in results.items():
        axes[0].plot(hist['val_loss'], label=name)
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Validation Loss (MSE)')
    axes[0].set_title('Validation Loss')
    axes[0].legend()

    # Spearman r curves
    for name, hist in results.items():
        axes[1].plot(hist['val_r'], label=name)
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Spearman ρ')
    axes[1].set_title('Validation Spearman r')
    axes[1].legend()
    axes[1].axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # Test r curves
    for name, hist in results.items():
        axes[2].plot(hist['test_r'], label=name)
    axes[2].set_xlabel('Epoch')
    axes[2].set_ylabel('Spearman ρ')
    axes[2].set_title('Test Spearman r')
    axes[2].legend()
    axes[2].axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig('ablation_results.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved: ablation_results.png")
except ImportError:
    print("matplotlib not available — skip plots")

# %% [markdown]
# ## 12. Save Best Model

# %%
# Save the best performing model
best_name = max(results.items(), key=lambda x: x[1].get('final_test_r', 0))[0]
print(f"Best model: {best_name} (test_r={results[best_name]['final_test_r']:.4f})")

if best_name == '3-hop GAT':
    best_model = gat_model
elif best_name == 'MLP':
    best_model = mlp_model
else:
    best_model = one_hop

torch.save({
    'model_state': best_model.cpu().state_dict(),
    'model_name': best_name,
    'test_r': results[best_name]['final_test_r'],
    'val_r': results[best_name]['final_val_r'],
    'n_nodes': data.num_nodes,
    'n_edges': data.num_edges,
    'n_features': data.num_node_features,
    'results': {k: {'final_val_r': v['final_val_r'], 'final_test_r': v['final_test_r'],
                     'elapsed': v['elapsed']} for k, v in results.items()},
}, 'gnn_twin_best.pt')
print("Saved: gnn_twin_best.pt")

# Download from Colab
# from google.colab import files
# files.download('gnn_twin_best.pt')
# files.download('ablation_results.png')

# %% [markdown]
# ## 13. Quick Sanity Check — Predictions vs Ground Truth

# %%
best_model = best_model.to(device)
best_model.eval()
with torch.no_grad():
    preds = best_model(data.x, data.edge_index).cpu().numpy()

print(f"Predictions: min={preds.min():.4f}, max={preds.max():.4f}, mean={preds.mean():.4f}")
print(f"Ground truth: min={labels.min():.4f}, max={labels.max():.4f}, mean={labels.mean():.4f}")
print(f"Segments with pred > 0.1: {(preds > 0.1).sum()} / {len(preds)}")
print(f"Segments with true > 0.1: {(labels > 0.1).sum()} / {len(labels)}")

# Correlation
overall_r, _ = spearmanr(preds, labels)
print(f"\nOverall Spearman r: {overall_r:.4f}")

# Top-K accuracy: do we identify the most impacted segments?
k = 1000
true_top_k = set(np.argsort(labels)[-k:])
pred_top_k = set(np.argsort(preds)[-k:])
overlap = len(true_top_k & pred_top_k)
print(f"Top-{k} overlap: {overlap}/{k} ({100*overlap/k:.1f}%)")
