# Phase 3: Graph Neural Network & Congestion Propagation ✅ COMPLETE

> **Goal**: Model how parking-induced congestion propagates through the road network  
> **Inputs**: `violations_enriched.parquet` (with PIS), OSM road graph  
> **Outputs**: GBM-36D model (r=0.59), Digital Twin simulation (2M vehicle-hours/day)  
> **Status**: ✅ COMPLETE — GBM outperformed GNN (r=0.59 vs r=0.24)

---

## 3.1 Road Network Graph Construction

### Step 3.1.1: Line Graph Transformation

```
File: drishtam/graph_builder.py → osm_to_line_graph()
```

**Concept**: In the OSM graph, roads are edges and intersections are nodes. For our GNN, we need roads as nodes (we want to score road segments). So we perform a **line graph transformation**:
- OSM edge (road segment) → Our node
- OSM node (intersection) → Our edge (connects road segments that share a junction)

**Tasks**:
- [ ] Load OSM graph `G`
- [ ] Extract all edges with their attributes (highway_type, lanes, width, length, name)
- [ ] For each pair of edges sharing a common OSM node, create a connection in our line graph
- [ ] Store edge-to-node mapping for later lookup
- [ ] Handle multigraph edges (OSM can have parallel edges between same nodes)

**Verification**:
- [ ] Number of nodes in line graph ≈ number of edges in OSM ≈ 393K
- [ ] Number of edges in line graph ≈ sum of (degree choose 2) at each intersection
- [ ] Graph is connected (or mostly connected — check largest component)
- [ ] Print: nodes, edges, average degree, diameter estimate

**📊 Visualization**:
- Network statistics summary plot (degree distribution, component sizes)
- Mini-map: a 2km×2km area showing the line graph overlaid on the road network

### Step 3.1.2: Node Feature Engineering

```
File: drishtam/graph_builder.py → build_node_features()
```

Each node (= road segment) gets an 12-dimensional feature vector:

| Feature | Dim | Source | Description |
|---|---|---|---|
| `lanes` | 1 | OSM | Number of lanes |
| `width` | 1 | OSM | Road width in meters |
| `road_tier` | 1 | Hierarchy | Tier 1-8 normalized |
| `length` | 1 | OSM | Segment length in meters |
| `is_link_road` | 1 | OSM | Binary: junction connector |
| `violation_count` | 1 | Data | Number of violations on this segment |
| `mean_pis` | 1 | Phase 2 | Mean PIS of violations on this segment |
| `max_pis` | 1 | Phase 2 | Max PIS of violations on this segment |
| `total_pis` | 1 | Phase 2 | Sum of PIS on this segment |
| `capacity_blocked_mean` | 1 | Data | Mean % of road blocked |
| `junction_degree_start` | 1 | OSM | Degree of start junction |
| `junction_degree_end` | 1 | OSM | Degree of end junction |

**Tasks**:
- [ ] Aggregate violation data per road segment (from Phase 1's `nearest_road_idx`)
- [ ] Compute statistics per segment: count, mean/max/sum PIS, mean capacity blocked
- [ ] Segments with zero violations get `violation_count=0, mean_pis=0, etc.`
- [ ] Normalize all features to [0, 1] or standardize (z-score)
- [ ] Store normalization parameters for inference

**Verification**:
- [ ] Feature matrix shape: (N_segments, 12)
- [ ] No NaN values (fill zeros for missing)
- [ ] Feature distributions are reasonable (plot histograms)
- [ ] Segments with known high violations (BSF STS Road) have high feature values

**📊 Visualization**:
- Feature correlation matrix (12×12 heatmap)
- Distributions of each feature (2×6 subplot grid)

### Step 3.1.3: Edge Feature Engineering

```
File: drishtam/graph_builder.py → build_edge_features()
```

Each edge in our line graph (= junction connecting two road segments) gets features:

| Feature | Dim | Source | Description |
|---|---|---|---|
| `junction_degree` | 1 | OSM | How many roads meet at this junction |
| `angle_between` | 1 | Geometry | Angle between the two road segments (0=straight, 90=turn) |

**Tasks**:
- [ ] For each connection, get the shared junction and its degree
- [ ] Compute angle between road segments using their geometries
- [ ] Normalize features

### Step 3.1.4: Build PyTorch Geometric Data Object

```
File: drishtam/graph_builder.py → build_pyg_data()
```

**Tasks**:
- [ ] Create `torch.Tensor` for node features: `x` (N, 12)
- [ ] Create `edge_index` tensor: (2, E) — COO format
- [ ] Create `edge_attr` tensor: (E, 2) — edge features
- [ ] Package as `torch_geometric.data.Data`
- [ ] Save to `data/road_graph.pt`
- [ ] Also save metadata: node-to-road-segment mapping, feature names, normalization params

**Verification**:
- [ ] `data.x.shape[0]` ≈ 393K
- [ ] `data.edge_index.shape[1]` > 0 (edges exist)
- [ ] `data.x` has no NaN
- [ ] Load test: can reload from `.pt` file

**📊 Visualization**:
- Graph summary: node count, edge count, average degree, density
- Degree histogram

---

## 3.2 Training Signal Construction

### Step 3.2.1: Ground Truth from Event Data

We don't have real traffic flow data, but we have **traffic events** as a proxy for congestion. We use event density around each road segment as a supervision signal.

```
File: drishtam/graph_builder.py → build_training_labels()
```

**Tasks**:
- [ ] For each road segment (node), count traffic events within 300m → `event_density`
- [ ] Normalize to [0, 1]
- [ ] This is our "ground truth" for congestion intensity per segment
- [ ] Alternative: use the grid-based quintile labels from EDA #3 (binary: high/low event zone)

**Important EDA question**: 
- [ ] Compute Spearman correlation between `mean_pis` (per segment) and `event_density` (per segment)
- Expected: r ≈ 0.3-0.5 (similar to grid-based r=0.41)
- If r < 0.2 → our PIS may need weight tuning before GNN training

**📊 Visualization**:
- Scatter: segment mean_pis vs event_density — with regression line
- Dual map: side-by-side of segment PIS vs event density on road network

### Step 3.2.2: Train/Validation/Test Split

**Tasks**:
- [ ] **Spatial split**: Use geographic regions (not random — avoid spatial leakage)
  - Train: West + South Bengaluru (60%)
  - Val: Central (20%)
  - Test: East + North (20%)
- [ ] Create train/val/test masks on the graph nodes
- [ ] Ensure each split has sufficient events for supervision

**Verification**:
- [ ] Each split has >10% of total events
- [ ] No spatial overlap between splits
- [ ] Road type distribution is similar across splits

**📊 Visualization**: Map showing train/val/test regions color-coded

---

## 3.3 Graph Attention Network (GAT) Model

### Step 3.3.1: Model Architecture

```
File: drishtam/propagation_model.py → class ParkImpactGAT
```

```
Architecture:
  Input (12 features per node)
    ↓
  GATConv(12 → 32, heads=4, concat=True) → 128-dim
    ↓ ReLU + Dropout(0.3)
  GATConv(128 → 32, heads=4, concat=True) → 128-dim  
    ↓ ReLU + Dropout(0.3)
  GATConv(128 → 16, heads=4, concat=False) → 16-dim
    ↓ ReLU
  Linear(16 → 1) → Propagated Impact Score
    ↓ Sigmoid → [0, 1]
```

**Design decisions**:
- **3 GAT layers** = 3-hop propagation (impact can spread to 3-neighboring road segments)
- **Multi-head attention** (4 heads) = model learns different types of propagation relationships
- **Dropout** = prevent overfitting on sparse event data
- **Sigmoid output** = bounded [0, 1] propagated impact score

**Tasks**:
- [ ] Implement `ParkImpactGAT(nn.Module)`
- [ ] Implement `forward(data)` method
- [ ] Add `get_attention_weights()` method for explainability (which neighbors matter most?)
- [ ] Parameter count: print and verify it's reasonable (<1M parameters)

### Step 3.3.2: Training Loop

```
File: drishtam/propagation_model.py → train_propagation_model()
```

**Tasks**:
- [ ] Loss: `MSELoss` between predicted propagated impact and event_density
- [ ] Optimizer: `Adam(lr=0.001, weight_decay=5e-4)`
- [ ] Scheduler: `ReduceLROnPlateau(patience=10, factor=0.5)`
- [ ] Train for up to 300 epochs, early stopping on val loss (patience=30)
- [ ] Log: train_loss, val_loss, val_correlation at each epoch
- [ ] Save best model checkpoint

**Verification**:
- [ ] Training loss decreases over epochs
- [ ] Val loss doesn't diverge (not overfitting)
- [ ] Val Spearman correlation > 0.3 (model learned something useful)
- [ ] Test Spearman correlation > 0.25 (generalizes to unseen areas)

**📊 Visualizations**:
1. **Training curves**: Loss vs epoch (train + val), correlation vs epoch
2. **Prediction scatter**: Predicted vs actual event density on test set
3. **Attention analysis**: Which neighbor types get highest attention weights?

### Step 3.3.3: Ablation Study

**Tasks**:
- [ ] Train with only PIS features (no road structure features) → baseline
- [ ] Train with only road features (no PIS) → how much does PIS add?
- [ ] Train with 1 GAT layer (1-hop) vs 2 (2-hop) vs 3 (3-hop) → propagation depth
- [ ] Compare: does the graph structure help vs. just using node features alone (MLP)?

**📊 Visualization**: Ablation comparison table/bar chart

---

## 3.4 Propagation Inference & Visualization

### Step 3.4.1: Full-City Propagation Scoring

```
File: drishtam/propagation_model.py → predict_propagation()
```

**Tasks**:
- [ ] Run trained model on full graph → propagated impact score per segment
- [ ] Segments with no violations may still have high propagated scores (impact from neighbors!)
- [ ] This is the key insight: "Road X has zero violations but high propagated impact because adjacent Road Y has 500 violations"
- [ ] Save propagated scores to parquet + add to road GeoDataFrame

**Verification**:
- [ ] All segments have a propagated score
- [ ] High-PIS segments should have high propagated scores
- [ ] Some zero-violation segments should have elevated propagated scores (network effect)
- [ ] Global mean propagated score should be lower than mean PIS (propagation dilutes)

**📊 Visualizations (KEY — these are the money shots)**:

1. **"The Congestion Ripple"**: Full Bengaluru road network colored by propagated impact score (gradient). Show how violations create "waves" of impact through the network.

2. **"Before vs After Propagation"**: Side-by-side maps:
   - Left: Road segments colored by direct PIS (only segments with violations are colored)
   - Right: Road segments colored by propagated impact (ALL segments colored)
   - Caption: "Left shows where violations ARE. Right shows where violations HURT."

3. **"The Hidden Victims"**: Highlight the top 50 road segments that have ZERO violations but HIGH propagated impact (>50th percentile). These are roads suffering from neighboring violations.

4. **"Propagation Cascade Example"**: Pick BSF STS Road. Show its direct impact, then 1-hop neighbors' propagated impact, then 2-hop, then 3-hop. Animated or 4-panel showing the decay.

5. **"Impact Heatmap Comparison"**: 
   - Map 1: Raw violation count heatmap (from EDA #1)
   - Map 2: PIS-weighted heatmap (from Phase 2)
   - Map 3: Propagated impact heatmap (new!)
   - Show how each layer adds more intelligence

### Step 3.4.2: Attention Weight Analysis (Explainability)

**Tasks**:
- [ ] Extract attention weights from trained GAT
- [ ] For each edge (road connection), get how much attention it receives
- [ ] Identify: which types of connections propagate impact most?
  - Major road → minor road? (high attention = violations on minor road spill to major)
  - Same-tier connections? (peer-to-peer propagation)
  - Link road connections? (junction propagation)

**📊 Visualization**:
- Network diagram (small area) with edge widths proportional to attention weights
- Bar chart: mean attention by road-tier-pair (e.g., "residential→tertiary" gets how much attention?)

---

## 3.5 Phase 3 Deliverables

| Deliverable | File | Description |
|---|---|---|
| Graph builder module | `drishtam/graph_builder.py` | OSM → PyG graph + features |
| Propagation model module | `drishtam/propagation_model.py` | GAT model + training + inference |
| Graph build script | `scripts/03_build_road_graph.py` | End-to-end graph construction |
| Trained model | `data/models/gat_propagation.pt` | Best GAT checkpoint |
| Graph data | `data/road_graph.pt` | PyG Data object |
| Propagated scores | `data/propagated_impact.parquet` | Per-segment propagated scores |
| Research report | `research/08_gnn_propagation.md` | Full findings + training results |
| Visualizations | `research/08_*.png` | 10+ charts including propagation maps |

### Exit Criteria:
- [ ] GAT model trains without errors
- [ ] Val Spearman r > 0.30 (model learned propagation patterns)
- [ ] Propagated scores computed for all ~393K segments
- [ ] "Hidden victims" analysis shows >100 zero-violation segments with elevated impact
- [ ] All 5 key propagation visualizations produced
- [ ] Ablation study complete
- [ ] Research report written
