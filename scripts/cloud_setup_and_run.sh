#!/bin/bash
set -e

echo "=== DRISHTAM Phase 1 — Cloud Pipeline ==="
echo "$(date): Starting setup..."

cd ~/drishtam_project

echo "Step 1: Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv libgdal-dev > /dev/null 2>&1
echo "  System packages installed"

echo "Step 2: Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "Step 3: Installing Python dependencies..."
pip install --quiet pandas numpy scipy osmnx geopandas matplotlib seaborn pyarrow
echo "  Python deps installed"

echo "Step 4: Verifying files..."
echo "  Files:"
ls -la *.csv data/*.graphml drishtam/*.py scripts/*.py pyproject.toml 2>/dev/null || echo "  Some files missing!"
echo ""
echo "  System RAM:"
free -h | head -3
echo ""

echo "Step 5: Testing imports..."
python3 -c "import pandas, numpy, scipy, osmnx, geopandas, matplotlib, seaborn; print('  All imports OK')"

echo ""
echo "Step 6: Running Phase 1 pipeline..."
python3 scripts/run_phase1.py

echo ""
echo "=== PIPELINE COMPLETE ==="
echo "Results:"
ls -la data/violations_enriched.parquet 2>/dev/null || echo "  Parquet not found!"
ls -la research/06_* 2>/dev/null || echo "  No research outputs found!"
