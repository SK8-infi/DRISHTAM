#!/bin/bash
set -e

PROJECT="/home/shiva/drishtam_project"

# System deps
sudo apt-get update -qq
sudo apt-get install -y -qq python3.10-venv python3-pip > /dev/null 2>&1

# Create dirs
mkdir -p $PROJECT/drishtam $PROJECT/scripts $PROJECT/data/models $PROJECT/research

# Python env
cd $PROJECT
python3 -m venv .venv
source .venv/bin/activate

# Install all deps
pip install --quiet numpy pandas pyarrow scipy scikit-learn matplotlib seaborn networkx hdbscan
pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
pip install --quiet torch_geometric

echo "=== ENV READY ==="
python3 -c "import torch; print(f'PyTorch {torch.__version__}')"
python3 -c "import torch_geometric; print(f'PyG {torch_geometric.__version__}')"
python3 -c "import os; print(f'CPU cores: {os.cpu_count()}')"
