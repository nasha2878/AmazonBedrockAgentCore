#!/bin/bash
set -e

echo "========================================="
echo "Starting OpsSyncAgent Lab Environment Setup"
echo "========================================="

# 1. Purge any pre-existing legacy node instances to avoid conflicts
echo "[1/4] Cleaning old Node.js environment paths..."
sudo dnf remove -y nodejs npm > /dev/null 2>&1 || true

# 2. Install the explicitly namespaced Node.js 20 package from internal mirrors
echo "[2/4] Installing native Node.js 20 components..."
sudo dnf install -y nodejs20

# 3. Environment Validation Pre-Check
echo "Validating system requirements..."
ACTIVE_NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)

if [ "$ACTIVE_NODE_VERSION" -lt 20 ]; then
    echo "ERROR: Environment check failed. Node version is below 20."
    echo "Active version: $(node -v)"
    exit 1
fi
echo "Environment check passed. Running Node: $(node -v)"

# 4. Register the framework engine tool globally
echo "[3/4] Registering AgentCore CLI engine..."
sudo npm install -g @aws/agentcore --no-audit --no-fund

# 5. Build clean application workspaces
echo "[4/4] Setting up project workspace..."
mkdir -p ~/AIOpsAgent
cd ~/AIOpsAgent

echo "========================================="
echo "Setup Complete!"
echo "AgentCore Engine: $(agentcore --version)"
echo "Target Workspace: ~/AIOpsAgent"
echo "========================================="
