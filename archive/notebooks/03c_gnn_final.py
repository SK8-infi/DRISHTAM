# %% [markdown]
# # DRISHTAM Phase 3C — ML Impact Prediction (Final Clean Notebook)
#
# **Pipeline**: OSM graph → line graph → spatial violation matching → betweenness
# centrality → 36D features → GBM/MLP training → subgraph experiments
#
# **Data files needed** (upload to Colab):
# - `bengaluru_roads.graphml` (144 MB)
# - `violations_enriched.parquet` (48 MB)
# - `delay_metrics.parquet` (7.5 MB)

# %% [markdown]
# ## 0. Setup

# %%
# !pip install torch-geometric torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.4.0+cu121.html
# !pip install networkx pandas pyarrow scipy scikit-learn

# %%
import os, time, ast, logging
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from scipy.stats import spearmanr
from scipy.spatial import cKDTree
from collections import defaultdict
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {device}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}, VRAM: {torch.cuda.get_device_properties(0).total_mem/1e9:.1f} GB")

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

# %% [markdown]
# ## 1. Data Paths

# %%
# --- Set paths (adjust for your setup) ---
# Option A: Colab upload
# from google.colab import files; uploaded = files.upload()
# Option B: Google Drive
# from google.colab import drive; drive.mount('/content/drive')
# DATA_DIR = '/content/drive/MyDrive/drishtam_data'
# Option C: Local
DATA_DIR = '.'

OSM_GRAPH_PATH = os.path.join(DATA_DIR, 'bengaluru_roads.graphml')
ENRICHED_DATA_PATH = os.path.join(DATA_DIR, 'violations_enriched.parquet')
DELAY_METRICS_PATH = os.path.join(DATA_DIR, 'delay_metrics.parquet')

for p in [OSM_GRAPH_PATH, ENRICHED_DATA_PATH, DELAY_METRICS_PATH]:
    exists = '✅' if os.path.exists(p) else '❌'
    sz = f"{os.path.getsize(p)/1e6:.1f} MB" if os.path.exists(p) else "MISSING"
    print(f"  {exists} {os.path.basename(p)}: {sz}")

# Road hierarchy used throughout
HIGHWAY_TIERS = {
    'motorway': 5, 'trunk': 4, 'primary': 3, 'secondary': 2, 'tertiary': 1,
    'motorway_link': 4, 'trunk_link': 3, 'primary_link': 2,
    'secondary_link': 1, 'tertiary_link': 1,
}

def parse_highway(hw):
    """Safely extract highway type from OSM data."""
    if isinstance(hw, list): hw = hw[0]
    if isinstance(hw, str) and hw.startswith('['):
        try: hw = ast.literal_eval(hw)[0]
        except: hw = 'residential'
    return hw

def safe_int(val, default=1):
    if val is None: return default
    if isinstance(val, (int, float)): return int(val)
    try: return int(str(val).strip())
    except ValueError:
        try:
            lst = ast.literal_eval(str(val))
            if isinstance(lst, list): return int(lst[0])
        except: pass
    return default

def safe_float(val, default=30.0):
    if val is None: return default
    if isinstance(val, (int, float)): return float(val)
    try: return float(str(val).strip())
    except ValueError:
        try:
            lst = ast.literal_eval(str(val))
            if isinstance(lst, list): return float(lst[0])
        except: pass
    return default

# %% [markdown]
# ## 2. Build Line Graph

# %%
import networkx as nx

def build_line_graph(osm_path):
    """OSM graph → line graph (roads=nodes, junctions=edges)."""
    G = nx.read_graphml(osm_path)
    print(f"OSM graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    segment_data = []
    for idx, (u, v, data) in enumerate(G.edges(data=True)):
        segment_data.append({
            'seg_idx': idx, 'osm_u': str(u), 'osm_v': str(v),
            'length_m': safe_float(data.get('length', 100), 100),
            'highway': data.get('highway', 'residential'),
            'lanes': safe_int(data.get('lanes', 1), 1),
            'maxspeed': safe_float(data.get('maxspeed', 30), 30.0),
            'name': data.get('name', ''),
            'oneway': str(data.get('oneway', 'False')).lower() in ('true', 'yes', '1'),
        })

    # Build adjacency
    node_to_segments = {}
    for seg in segment_data:
        for node in [seg['osm_u'], seg['osm_v']]:
            node_to_segments.setdefault(node, []).append(seg['seg_idx'])

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

    # Get node coordinates for spatial matching later
    node_coords = {}
    for n, d in G.nodes(data=True):
        if 'y' in d and 'x' in d:
            node_coords[str(n)] = (float(d['y']), float(d['x']))

    print(f"Line graph: {len(segment_data)} nodes, {len(edge_src)//2} edges")
    return segment_data, (edge_src, edge_dst), node_coords

t0 = time.time()
segment_data, edge_list, node_coords = build_line_graph(OSM_GRAPH_PATH)
N = len(segment_data)
print(f"Built in {time.time()-t0:.1f}s")

# %% [markdown]
# ## 3. Load Targets (from v6 simulation)

# %%
df_delay = pd.read_parquet(DELAY_METRICS_PATH)
print(f"Delay metrics: {df_delay.shape}, columns: {list(df_delay.columns)}")

raw_target = df_delay['impact_score'].values
labels = np.zeros(N, dtype=np.float32)
labels[:min(len(raw_target), N)] = raw_target[:min(len(raw_target), N)]
labels = np.maximum(labels, 0)
labels = np.log1p(labels)
lmax = labels.max()
if lmax > 0: labels /= lmax

print(f"Labels: {(labels>0).sum()}/{N} positive ({100*(labels>0).sum()/N:.1f}%), "
      f"mean={labels.mean():.4f}, max={labels.max():.4f}")
del df_delay

# %% [markdown]
# ## 4. Spatial Violation Matching (KDTree)

# %%
# Build segment midpoints
seg_lats = np.zeros(N, dtype=np.float64)
seg_lons = np.zeros(N, dtype=np.float64)
for i, seg in enumerate(segment_data):
    u_c = node_coords.get(seg['osm_u'])
    v_c = node_coords.get(seg['osm_v'])
    if u_c and v_c:
        seg_lats[i] = (u_c[0] + v_c[0]) / 2
        seg_lons[i] = (u_c[1] + v_c[1]) / 2

tree = cKDTree(np.column_stack([seg_lats, seg_lons]))

# Match violations to nearest segment
df_viol = pd.read_parquet(ENRICHED_DATA_PATH)
viol_lats = df_viol['latitude'].values
viol_lons = df_viol['longitude'].values
valid = ~(np.isnan(viol_lats) | np.isnan(viol_lons))
dists, indices = tree.query(np.column_stack([viol_lats[valid], viol_lons[valid]]), k=1)

seg_violation_count = np.zeros(N, dtype=np.float32)
seg_max_pis = np.zeros(N, dtype=np.float32)
seg_capacity_blocked = np.zeros(N, dtype=np.float32)
seg_peak_violations = np.zeros(N, dtype=np.float32)
seg_mean_severity = np.zeros(N, dtype=np.float32)

pis_v = df_viol.loc[valid, 'pis'].values if 'pis' in df_viol.columns else np.zeros(valid.sum())
cap_v = df_viol.loc[valid, 'capacity_blocked_pct'].values if 'capacity_blocked_pct' in df_viol.columns else np.zeros(valid.sum())
sev_v = df_viol.loc[valid, 'violation_severity'].values if 'violation_severity' in df_viol.columns else np.ones(valid.sum())
peak_m = df_viol.loc[valid, 'is_peak_morning'].values if 'is_peak_morning' in df_viol.columns else np.zeros(valid.sum())
peak_e = df_viol.loc[valid, 'is_peak_evening'].values if 'is_peak_evening' in df_viol.columns else np.zeros(valid.sum())

MATCH_THRESHOLD = 0.001  # ~100m
for j in range(len(indices)):
    if dists[j] < MATCH_THRESHOLD:
        idx = indices[j]
        seg_violation_count[idx] += 1
        if not np.isnan(pis_v[j]): seg_max_pis[idx] = max(seg_max_pis[idx], float(pis_v[j]))
        if not np.isnan(cap_v[j]): seg_capacity_blocked[idx] = max(seg_capacity_blocked[idx], float(cap_v[j]))
        if not np.isnan(sev_v[j]): seg_mean_severity[idx] += float(sev_v[j])
        p = (float(peak_m[j]) if not np.isnan(peak_m[j]) else 0) + \
            (float(peak_e[j]) if not np.isnan(peak_e[j]) else 0)
        seg_peak_violations[idx] += p

mask_v = seg_violation_count > 0
seg_mean_severity[mask_v] /= seg_violation_count[mask_v]
print(f"Matched violations to {mask_v.sum()} segments ({100*mask_v.sum()/N:.1f}%), "
      f"total violations: {int(seg_violation_count.sum())}")
del df_viol

# %% [markdown]
# ## 5. Betweenness Centrality (GPU-accelerated)

# %%
# !pip install cugraph-cu12 --extra-index-url https://pypi.nvidia.com

# %%
try:
    import cugraph
    import cudf

    # Build edge list for cuGraph
    G_nx = nx.read_graphml(OSM_GRAPH_PATH)
    edges_u, edges_v, weights = [], [], []
    for u, v, d in G_nx.edges(data=True):
        try: w = float(d.get('length', 100))
        except: w = 100.0
        edges_u.append(int(u))
        edges_v.append(int(v))
        weights.append(w)

    gdf = cudf.DataFrame({'src': edges_u, 'dst': edges_v, 'weight': weights})
    G_cu = cugraph.Graph()
    G_cu.from_cudf_edgelist(gdf, source='src', destination='dst', edge_attr='weight')

    t0 = time.time()
    bc_df = cugraph.betweenness_centrality(G_cu, k=1000, normalized=True)
    print(f"GPU betweenness: {time.time()-t0:.1f}s ✅")

    # Map to segments
    bc_map = dict(zip(bc_df['vertex'].to_pandas().astype(str),
                       bc_df['betweenness_centrality'].to_pandas()))
    seg_betweenness = np.zeros(N, dtype=np.float32)
    for i, seg in enumerate(segment_data):
        seg_betweenness[i] = (bc_map.get(seg['osm_u'], 0) + bc_map.get(seg['osm_v'], 0)) / 2

    del G_nx, G_cu, gdf, bc_df

except (ImportError, Exception) as e:
    print(f"cuGraph not available ({e}), falling back to NetworkX CPU...")

    G = nx.read_graphml(OSM_GRAPH_PATH)
    for u, v, d in G.edges(data=True):
        try: d['length'] = float(d.get('length', 100))
        except: d['length'] = 100.0

    t0 = time.time()
    bc = nx.betweenness_centrality(G, k=min(1000, G.number_of_nodes()),
                                     weight='length', normalized=True)
    print(f"CPU betweenness: {time.time()-t0:.1f}s")

    seg_betweenness = np.zeros(N, dtype=np.float32)
    for i, seg in enumerate(segment_data):
        seg_betweenness[i] = (bc.get(seg['osm_u'], 0) + bc.get(seg['osm_v'], 0)) / 2
    del G, bc

bc_r, _ = spearmanr(seg_betweenness, labels)
print(f"Betweenness → impact: r={bc_r:.4f}")

# %% [markdown]
# ## 6. Neighborhood Aggregation (1-hop + 2-hop)

# %%
# 1-hop
nbr_viol_sum = np.zeros(N, dtype=np.float32)
nbr_pis_max = np.zeros(N, dtype=np.float32)
nbr_cap_max = np.zeros(N, dtype=np.float32)
nbr_count = np.zeros(N, dtype=np.float32)

for s, d in zip(edge_list[0], edge_list[1]):
    nbr_viol_sum[d] += seg_violation_count[s]
    nbr_pis_max[d] = max(nbr_pis_max[d], seg_max_pis[s])
    nbr_cap_max[d] = max(nbr_cap_max[d], seg_capacity_blocked[s])
    nbr_count[d] += 1

nbr_viol_avg = np.divide(nbr_viol_sum, nbr_count, where=nbr_count > 0,
                          out=np.zeros(N, dtype=np.float32))

# 2-hop
adj = defaultdict(set)
for s, d in zip(edge_list[0], edge_list[1]):
    adj[d].add(s)

nbr2_viol = np.zeros(N, dtype=np.float32)
nbr2_pis = np.zeros(N, dtype=np.float32)
nbr2_bc = np.zeros(N, dtype=np.float32)

for node in range(N):
    hop1 = adj[node]
    hop2 = set()
    for n1 in hop1: hop2.update(adj[n1])
    hop2.discard(node)
    hop2 -= hop1
    if hop2:
        for n2 in hop2:
            nbr2_viol[node] += seg_violation_count[n2]
            nbr2_pis[node] = max(nbr2_pis[node], seg_max_pis[n2])
            nbr2_bc[node] += seg_betweenness[n2]
        nbr2_viol[node] /= len(hop2)
        nbr2_bc[node] /= len(hop2)

print(f"1-hop coverage: {(nbr_viol_sum > 0).sum()} | 2-hop coverage: {(nbr2_viol > 0).sum()}")

# %% [markdown]
# ## 7. Build 36D Feature Matrix

# %%
# Road capacity (IRC standards)
CAP_PER_LANE = {'motorway': 1800, 'trunk': 1500, 'primary': 1200, 'secondary': 900,
                'tertiary': 600, 'residential': 400, 'motorway_link': 1500,
                'trunk_link': 1200, 'primary_link': 900, 'secondary_link': 600, 'tertiary_link': 400}

seg_capacity = np.array([
    CAP_PER_LANE.get(parse_highway(seg.get('highway','residential')), 400) * seg.get('lanes', 1)
    for seg in segment_data
], dtype=np.float32)

# Violation density
seg_viol_density = np.zeros(N, dtype=np.float32)
for i, seg in enumerate(segment_data):
    L = seg.get('length_m', 100)
    if L > 0 and seg_violation_count[i] > 0:
        seg_viol_density[i] = seg_violation_count[i] / (L / 100)

# Build full 36D feature matrix
features = np.zeros((N, 36), dtype=np.float32)
for i, seg in enumerate(segment_data):
    hw = parse_highway(seg.get('highway', 'residential'))
    tier = HIGHWAY_TIERS.get(hw, 0)

    # Road (0-8)
    features[i, 0] = np.log1p(seg.get('length_m', 100))
    features[i, 1] = seg.get('lanes', 1)
    features[i, 2] = seg.get('maxspeed', 30) / 120.0
    features[i, 3] = tier / 5.0
    features[i, 4] = float(seg.get('oneway', False))
    features[i, 5] = np.log1p(seg.get('junction_degree_start', 1))
    features[i, 6] = np.log1p(seg.get('junction_degree_end', 1))
    features[i, 7] = np.log1p(seg_capacity[i])
    features[i, 8] = seg_betweenness[i] * 1000

    # Local violations (9-15)
    features[i, 9]  = np.log1p(seg_violation_count[i])
    features[i, 10] = seg_max_pis[i]
    features[i, 11] = float(seg_violation_count[i] > 0)
    features[i, 12] = seg_capacity_blocked[i]
    features[i, 13] = np.log1p(seg_peak_violations[i])
    features[i, 14] = seg_viol_density[i]
    features[i, 15] = seg_mean_severity[i]

    # 1-hop (16-20)
    features[i, 16] = np.log1p(nbr_viol_sum[i])
    features[i, 17] = nbr_pis_max[i]
    features[i, 18] = nbr_cap_max[i]
    features[i, 19] = nbr_viol_avg[i]
    features[i, 20] = np.log1p(nbr_count[i])

    # 2-hop (21-23)
    features[i, 21] = np.log1p(nbr2_viol[i])
    features[i, 22] = nbr2_pis[i]
    features[i, 23] = nbr2_bc[i] * 1000

    # Interactions (24-35)
    features[i, 24] = features[i, 3] * features[i, 9]
    features[i, 25] = features[i, 1] * features[i, 12]
    features[i, 26] = features[i, 3] * features[i, 16]
    features[i, 27] = features[i, 9] * features[i, 16]
    features[i, 28] = features[i, 8] * features[i, 9]
    features[i, 29] = features[i, 8] * features[i, 3]
    features[i, 30] = features[i, 7] * features[i, 12]
    features[i, 31] = features[i, 14] * features[i, 3]
    features[i, 32] = features[i, 8] * features[i, 16]
    features[i, 33] = features[i, 3] * features[i, 4]
    features[i, 34] = features[i, 7] * features[i, 9]
    features[i, 35] = features[i, 8] * features[i, 12]

features = np.nan_to_num(features, 0.0)

FEAT_NAMES = ['log_len','lanes','speed','tier','oneway','jdeg_s','jdeg_e','capacity','betweenness',
    'viol_cnt','pis','has_v','cap_blk','peak_v','viol_dens','severity',
    'nbr1_v','nbr1_pis','nbr1_cap','nbr1_avg','degree',
    'nbr2_v','nbr2_pis','nbr2_bc',
    't×v','l×c','t×nv','v×nv','bc×v','bc×t','cap×cb','dens×t','bc×nv','t×ow','cap×v','bc×cb']

print(f"Features: {features.shape}")
print("\nTop correlations with impact_score:")
cors = [(FEAT_NAMES[i], spearmanr(features[:, i], labels)[0]) for i in range(36)]
cors.sort(key=lambda x: -abs(x[1]))
for name, r in cors[:10]:
    print(f"  {name:>12}: r={r:+.4f}")

# %% [markdown]
# ## 8. Train/Val/Test Split

# %%
def build_split(labels, train_ratio=0.6, val_ratio=0.2, seed=42):
    n = len(labels)
    affected = np.where(labels > 0)[0]
    unaffected = np.where(labels == 0)[0]
    n_sample = min(len(affected), len(unaffected))
    rng = np.random.RandomState(seed)
    if len(unaffected) > n_sample:
        unaffected = rng.choice(unaffected, n_sample, replace=False)
    all_idx = np.concatenate([affected, unaffected])
    rng.shuffle(all_idx)
    n_train = int(len(all_idx) * train_ratio)
    n_val = int(len(all_idx) * val_ratio)
    train_mask = np.zeros(n, dtype=bool); train_mask[all_idx[:n_train]] = True
    val_mask = np.zeros(n, dtype=bool);   val_mask[all_idx[n_train:n_train+n_val]] = True
    test_mask = np.zeros(n, dtype=bool);  test_mask[all_idx[n_train+n_val:]] = True
    print(f"Split: {train_mask.sum()} train, {val_mask.sum()} val, {test_mask.sum()} test")
    return train_mask, val_mask, test_mask

train_mask, val_mask, test_mask = build_split(labels)

# %% [markdown]
# ## 9. Model Definitions

# %%
from torch_geometric.data import Data
from torch_geometric.nn import GATConv

class MLPModel(nn.Module):
    def __init__(self, in_ch=36, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_ch, hidden), nn.BatchNorm1d(hidden), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(hidden, hidden), nn.BatchNorm1d(hidden), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(hidden, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )
    def forward(self, x, edge_index=None):
        return torch.clamp(self.net(x).squeeze(-1), 0, 1)

class TinyGAT(nn.Module):
    def __init__(self, in_ch=36, hidden=16, heads=2, dropout=0.3):
        super().__init__()
        self.dropout = dropout
        self.conv1 = GATConv(in_ch, hidden, heads=heads, concat=False, dropout=dropout)
        self.bn1 = nn.BatchNorm1d(hidden)
        self.conv2 = GATConv(hidden, hidden, heads=heads, concat=False, dropout=dropout)
        self.out = nn.Linear(hidden, 1)
    def forward(self, x, edge_index):
        x = F.elu(self.bn1(self.conv1(x, edge_index)))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = F.elu(self.conv2(x, edge_index))
        return torch.clamp(self.out(x).squeeze(-1), 0, 1)

def train_model(model, data, name="Model", max_epochs=200, patience=30, lr=0.001):
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
    criterion = nn.SmoothL1Loss()
    best_val, best_state, no_improve = float('inf'), None, 0
    hist = {'train_loss':[], 'val_loss':[], 'val_r':[], 'test_r':[]}

    print(f"\n{'='*60}\n{name}: {sum(p.numel() for p in model.parameters())} params\n{'='*60}")
    t0 = time.time()
    for epoch in range(max_epochs):
        model.train(); optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        loss = criterion(out[data.train_mask], data.y[data.train_mask])
        loss.backward(); optimizer.step()

        model.eval()
        with torch.no_grad():
            out = model(data.x, data.edge_index)
            vl = criterion(out[data.val_mask], data.y[data.val_mask]).item()
            vr, _ = spearmanr(out[data.val_mask].cpu().numpy(), data.y[data.val_mask].cpu().numpy())
            tr, _ = spearmanr(out[data.test_mask].cpu().numpy(), data.y[data.test_mask].cpu().numpy())
        scheduler.step(vl)
        hist['train_loss'].append(loss.item()); hist['val_loss'].append(vl)
        hist['val_r'].append(float(vr)); hist['test_r'].append(float(tr))

        if vl < best_val:
            best_val = vl; best_state = {k: v.clone() for k, v in model.state_dict().items()}; no_improve = 0; m = '★'
        else: no_improve += 1; m = ''
        if epoch % 20 == 0 or m: print(f"  Ep {epoch:3d}: val_r={vr:.3f} test_r={tr:.3f} {m}")
        if no_improve >= patience: print(f"  Early stop ep {epoch}"); break

    if best_state: model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out = model(data.x, data.edge_index)
        fvr, _ = spearmanr(out[data.val_mask].cpu().numpy(), data.y[data.val_mask].cpu().numpy())
        ftr, _ = spearmanr(out[data.test_mask].cpu().numpy(), data.y[data.test_mask].cpu().numpy())
    print(f"  ▶ {name}: val_r={fvr:.4f}, test_r={ftr:.4f} ({time.time()-t0:.1f}s)")
    hist['final_val_r'] = fvr; hist['final_test_r'] = ftr; hist['elapsed'] = time.time()-t0
    return model, hist

# %% [markdown]
# ## 10. Full Network Training (Baseline)

# %%
features_scaled = StandardScaler().fit_transform(features).astype(np.float32)

# GBM
t0 = time.time()
gbm = GradientBoostingRegressor(n_estimators=500, max_depth=8, learning_rate=0.03,
    subsample=0.8, min_samples_leaf=30, max_features=0.8, random_state=42)
gbm.fit(features_scaled[train_mask], labels[train_mask])
gbm_preds = gbm.predict(features_scaled)
gbm_vr, _ = spearmanr(gbm.predict(features_scaled[val_mask]), labels[val_mask])
gbm_tr, _ = spearmanr(gbm.predict(features_scaled[test_mask]), labels[test_mask])
print(f"GBM-36D: val_r={gbm_vr:.4f}, test_r={gbm_tr:.4f} ({time.time()-t0:.1f}s)")

print("\nTop features:")
for idx in np.argsort(gbm.feature_importances_)[::-1][:8]:
    print(f"  {FEAT_NAMES[idx]:>12}: {gbm.feature_importances_[idx]:.4f}")

# MLP
data_pyg = Data(
    x=torch.tensor(features_scaled, dtype=torch.float32),
    edge_index=torch.tensor([edge_list[0], edge_list[1]], dtype=torch.long),
    y=torch.tensor(labels, dtype=torch.float32),
    train_mask=torch.tensor(train_mask, dtype=torch.bool),
    val_mask=torch.tensor(val_mask, dtype=torch.bool),
    test_mask=torch.tensor(test_mask, dtype=torch.bool),
).to(device)

mlp, mlp_h = train_model(MLPModel(36, 256), data_pyg, "MLP-36D", max_epochs=300, patience=40, lr=0.0005)

# %% [markdown]
# ## 11. Top-K Analysis (Full Network)

# %%
mlp.eval()
with torch.no_grad():
    mlp_preds = mlp(data_pyg.x, data_pyg.edge_index).cpu().numpy()

ensemble_preds = (gbm_preds + mlp_preds) / 2
ens_r, _ = spearmanr(ensemble_preds[test_mask], labels[test_mask])

print(f"\n{'='*70}\nFULL NETWORK RESULTS\n{'='*70}")
print(f"{'Model':<20} {'Test r':>8} {'Top-100':>10} {'Top-500':>10} {'Top-1K':>10} {'Top-5K':>10}")
print("-" * 65)

for name, preds in [('GBM-36D', gbm_preds), ('MLP-36D', mlp_preds), ('Ensemble', ensemble_preds)]:
    r, _ = spearmanr(preds[test_mask], labels[test_mask])
    tks = []
    for k in [100, 500, 1000, 5000]:
        overlap = len(set(np.argsort(labels)[-k:]) & set(np.argsort(preds)[-k:]))
        tks.append(f"{100*overlap/k:.1f}%")
    print(f"{name:<20} {r:>8.4f} {tks[0]:>10} {tks[1]:>10} {tks[2]:>10} {tks[3]:>10}")

# %% [markdown]
# ## 12. Subgraph Experiment — Does focusing on relevant roads help?

# %%
has_violations = seg_violation_count > 0
has_impact = labels > 0
is_major = np.array([HIGHWAY_TIERS.get(parse_highway(seg.get('highway','residential')), 0) >= 1
                      for seg in segment_data])
has_nbr_violations = nbr_viol_sum > 0
has_betweenness = seg_betweenness > np.percentile(seg_betweenness[seg_betweenness > 0], 25) if (seg_betweenness > 0).any() else np.zeros(N, dtype=bool)

subgraphs = {
    'Full network':              np.ones(N, dtype=bool),
    'Major roads (tier≥1)':      is_major,
    'Has impact (>0)':           has_impact,
    'Violations + 1-hop':        has_violations | has_nbr_violations,
    'Major + viol + 1-hop':      is_major | has_violations | (has_nbr_violations & is_major),
    'Major + high betweenness':  is_major & has_betweenness,
    'Impact>0 + major':          has_impact & is_major,
}

print(f"{'Subgraph':<30} {'Segments':>10} {'%':>6} {'Positive':>10} {'%pos':>6}")
print("-" * 65)
for name, mask in subgraphs.items():
    n = mask.sum(); n_pos = (labels[mask] > 0).sum()
    print(f"{name:<30} {n:>10} {100*n/N:>5.1f}% {n_pos:>10} {100*n_pos/max(n,1):>5.1f}%")

# %%
print(f"\n{'='*70}\nSUBGRAPH GBM TRAINING\n{'='*70}")

sub_results = {}
for sub_name, sub_mask in subgraphs.items():
    sub_idx = np.where(sub_mask)[0]
    n_sub = len(sub_idx)
    sub_feat = features_scaled[sub_idx]
    sub_lab = labels[sub_idx]
    n_pos = (sub_lab > 0).sum()
    if n_sub < 1000 or n_pos < 100:
        print(f"\n{sub_name}: skip ({n_sub} segs, {n_pos} pos)")
        continue

    # Balanced split
    aff = np.where(sub_lab > 0)[0]
    unaff = np.where(sub_lab == 0)[0]
    ns = min(len(aff), len(unaff))
    rng = np.random.RandomState(42)
    if len(unaff) > ns: unaff = rng.choice(unaff, ns, replace=False)
    all_i = np.concatenate([aff, unaff]); rng.shuffle(all_i)
    nt = int(len(all_i)*0.6); nv = int(len(all_i)*0.2)
    s_train = np.zeros(n_sub, dtype=bool); s_train[all_i[:nt]] = True
    s_val = np.zeros(n_sub, dtype=bool); s_val[all_i[nt:nt+nv]] = True
    s_test = np.zeros(n_sub, dtype=bool); s_test[all_i[nt+nv:]] = True

    t0 = time.time()
    g = GradientBoostingRegressor(n_estimators=500, max_depth=8, learning_rate=0.03,
        subsample=0.8, min_samples_leaf=30, max_features=0.8, random_state=42)
    g.fit(sub_feat[s_train], sub_lab[s_train])
    p_all = g.predict(sub_feat)
    tr, _ = spearmanr(g.predict(sub_feat[s_test]), sub_lab[s_test])

    topk = {}
    for k in [100, 500, 1000]:
        if k >= n_sub: continue
        topk[k] = len(set(np.argsort(sub_lab)[-k:]) & set(np.argsort(p_all)[-k:])) / k

    sub_results[sub_name] = {'n': n_sub, 'test_r': tr, 'topk': topk, 'time': time.time()-t0}
    tk_s = ' | '.join([f"Top-{k}: {100*v:.1f}%" for k, v in topk.items()])
    print(f"\n{sub_name} ({n_sub}):\n  r={tr:.4f} | {tk_s} | {time.time()-t0:.0f}s")

# %%
print(f"\n{'='*70}\nSUBGRAPH COMPARISON\n{'='*70}")
print(f"{'Subgraph':<30} {'N':>8} {'Test r':>8} {'Top-100':>8} {'Top-500':>8} {'Top-1K':>8}")
print("-" * 70)
for name, r in sorted(sub_results.items(), key=lambda x: -x[1]['test_r']):
    t100 = f"{100*r['topk'].get(100,0):.1f}%" if 100 in r['topk'] else "—"
    t500 = f"{100*r['topk'].get(500,0):.1f}%" if 500 in r['topk'] else "—"
    t1k  = f"{100*r['topk'].get(1000,0):.1f}%" if 1000 in r['topk'] else "—"
    print(f"{name:<30} {r['n']:>8} {r['test_r']:>8.4f} {t100:>8} {t500:>8} {t1k:>8}")

# %% [markdown]
# ## 13. Save Best Model

# %%
import joblib
joblib.dump(gbm, 'gbm_36d_best.pkl')
print("Saved: gbm_36d_best.pkl")

torch.save({
    'model_state': mlp.cpu().state_dict(),
    'n_features': 36, 'feature_names': FEAT_NAMES,
    'test_r': mlp_h['final_test_r'],
}, 'mlp_36d_best.pt')
print("Saved: mlp_36d_best.pt")

# Download from Colab:
# from google.colab import files
# files.download('gbm_36d_best.pkl')
# files.download('mlp_36d_best.pt')
