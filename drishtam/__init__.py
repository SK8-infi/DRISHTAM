# DRISHTAM — AI-Driven Parking Congestion Intelligence
"""DRISHTAM (दृष्टम्): That which has been revealed.

A unified AI platform that scores every parking violation's congestion impact,
models how that impact propagates through the road network, and predicts
where tomorrow's worst violations will occur.

Modules:
    config: Central configuration (paths, constants, hyperparameters)
    data_pipeline: Data loading, cleaning, and enrichment
    impact_scorer: Parking Impact Score (PIS) computation
    graph_builder: OSM road network to PyTorch Geometric graph
    propagation_model: GAT-based congestion propagation
    counterfactual: What-if scenario simulation
    risk_forecaster: Spatio-temporal risk prediction
    clustering: HDBSCAN hotspot detection
    exceptions: Custom exception hierarchy
    verification: Data quality gate checks
    utils: Shared utilities
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "DRISHTAM Team"
