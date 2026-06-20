# 08 — GNN Propagation: Graph Attention Network for Impact Spreading

> **Phase**: 3A — Graph Neural Network Propagation  
> **Date**: June 17-18, 2026  
> **Compute**: GCP e2-highmem-8 VM (8 vCPU, 64GB RAM, asia-south1-a)  
> **Runtime**: ~22 minutes training (70 epochs), ~2 hours total with ablation

---

## Objective

Can we use Graph Neural Networks to propagate parking impact scores (PIS) through the road network — i.e., can a violation on one road affect scores on neighboring roads?

**Hypothesis**: Violations on arterial roads should propagate congestion to downstream feeder roads. A GNN operating on the OSM road graph should capture this spatial spillover.

## Network Statistics

| Metric | Value |
|--------|-------|
| Nodes (road segments) | 393,717 |
| Edges (adjacency links) | 3,809,006 |
| Mean degree | 9.7 |
| Max degree | 18 |
| Node features | 12 per node |
| Nodes with violations | 94,667 (24%) |
| Nodes without violations | 299,050 (76%) |

### Node Features (12 total)

| # | Feature | Source |
|---|---------|--------|
| 1 | PIS score (normalized) | Phase 2 |
| 2 | Violation count (log) | Phase 1 |
| 3 | Mean capacity blocked (%) | Phase 2 |
| 4 | Road width (meters) | OSM |
| 5 | Lane count | OSM |
| 6 | Road length (meters) | OSM |
| 7 | Road tier (encoded) | OSM highway tag |
| 8 | Is link road | OSM |
| 9 | Speed limit (km/h) | OSM / defaults |
| 10 | Junction degree (max endpoint) | OSM graph |
| 11 | Mean violation duration (hours) | Phase 1 |
| 12 | Peak hour fraction | Phase 1 |

## Experiments

### 5-Way Ablation Study

| Model | Config | Val Spearman r | Test Spearman r |
|-------|--------|----------------|-----------------|
| **Full GNN (3-hop GAT)** | 3 GAT layers, all features | 0.220 | 0.232 |
| **PIS-only GNN** | GAT, only PIS-related features | 0.220 | 0.232 |
| **Road-only GNN** | GAT, only road features (no PIS) | -0.003 | 0.002 |
| **MLP Baseline** | No graph, all features | **0.586** | **0.594** |
| **GNN 1-hop** | 1 GAT layer, all features | 0.238 | 0.241 |

### Training Configuration

- **Model**: GAT (Graph Attention Network) with 2 attention heads
- **Hidden dim**: 64
- **Epochs**: 70 (early stopping patience: 20)
- **Optimizer**: Adam, lr=0.001, cosine annealing
- **Loss**: MSE
- **Split**: 70/15/15 (random)

## Key Findings

### 1. MLP Dominates GNN (r=0.59 vs r=0.24)

The MLP baseline **massively outperforms** all GNN variants. This is the most important finding:

- **PIS is a local phenomenon**: A violation's impact is almost entirely determined by its own features (road width, duration, vehicle type), not by what's happening on neighboring roads.
- The GNN's message passing actually **hurts** performance — it averages the node's features with its neighbors, diluting the signal.

### 2. Road Features Alone Are Useless (r ≈ 0)

The "road-only" GNN (no PIS features) achieves r ≈ 0. This means:
- Road geometry alone cannot predict where high-impact violations will be
- Impact is driven by the violations themselves, not the road they're on
- This makes intuitive sense: a wide road CAN have a high-impact violation if someone parks a truck on it

### 3. 7,181 "Hidden Victims" Discovered

The GNN did find 7,181 segments with **zero direct violations** but elevated propagated scores. These are roads that suffer congestion spillover from nearby violations. While the overall r is low, this qualitative finding is valuable.

### 4. Graph Structure Adds Marginal Value

Comparing 1-hop (r=0.241) vs 3-hop (r=0.232) GNN:
- More hops = slightly worse performance
- The optimal receptive field for PIS propagation is very local (immediate neighbors only)
- Long-range propagation patterns are not captured by the current target variable

## Propagation Output

The GNN propagated scores to all 393,717 segments:

| Metric | Value |
|--------|-------|
| Segments with direct PIS | 94,667 |
| Segments with propagated PIS > 0 | 101,848 |
| Hidden victims (no violations, PIS > 0) | 7,181 |
| Mean direct PIS | 0.609 |
| Mean propagated PIS | 0.593 |

Output saved: `data/propagated_impact.parquet`

## Root Cause Analysis: Why GNN Fails

The fundamental issue is the **target variable**. We trained the GNN to predict PIS from features that already CONTAIN PIS. This is circular:

```
Target = PIS score
Features = [PIS, violation_count, capacity_blocked, ...]
Result = MLP just memorizes input PIS → r=0.59
         GNN dilutes PIS with neighbor averages → r=0.24
```

**The fix**: Use the Digital Twin's `delta_delay` (physics-based traffic impact) as the new target variable. This gives the GNN something genuinely spatial to learn — how violations on one road cause delays on neighboring roads through traffic rerouting.

## Visualizations

| Chart | File |
|-------|------|
| Ablation study | `research/08_ablation_study.png` |
| Training curves | `research/08_training_curves.png` |
| Pred vs actual | `research/08_pred_vs_actual.png` |
| Propagated distribution | `research/08_propagated_distribution.png` |
| Hidden victims | `research/08_hidden_victims.png` |
| Feature distributions | `research/08_feature_distributions.png` |
| Degree distribution | `research/08_degree_distribution.png` |
| Road type breakdown | `research/08_propagation_by_road_type.png` |
| Summary card | `research/08_graph_summary.png` |

## Next Steps

1. ✅ Digital Twin simulation (Phase 3B) — generates physics-based target variable
2. ⬜ Re-train GNN with `delta_delay` target from twin
3. ⬜ Expected: r should jump from 0.24 → 0.5+ with meaningful spatial signal
