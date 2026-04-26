#!/bin/bash
# ==========================================
# Python Environment Setup (Agent + Client)
# ==========================================

set -e

echo "=== Creating virtual environment ==="
python3 -m venv agent-env

echo "=== Activate with: source agent-env/bin/activate ==="
echo "Now activating temporarily to install dependencies..."

source agent-env/bin/activate

echo "=== Upgrading pip ==="
pip install --upgrade pip

echo "=== Installing boto3 ==="
pip install boto3

echo "=== Verifying AgentCore Services ==="
python - <<EOF
import boto3
s = boto3.session.Session()
print("bedrock-agentcore-control:", "bedrock-agentcore-control" in s.get_available_services())
print("bedrock-agentcore:", "bedrock-agentcore" in s.get_available_services())
EOF

echo "=== Python Environment Setup Complete ==="
echo "IMPORTANT: After this script finishes, run:"
echo "source agent-env/bin/activate"
