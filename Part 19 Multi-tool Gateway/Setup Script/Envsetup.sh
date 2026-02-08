#!/bin/bash
# =============================================
# Setup Script: Ubuntu Core Utilities, Python 3, AWS CLI v2, Docker-ready
# Supports x86_64 and ARM64
# =============================================

set -e
set -o pipefail

echo "=== Updating system packages ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installing core utilities ==="
sudo apt install -y \
  ca-certificates \
  curl \
  unzip \
  gnupg \
  lsb-release \
  jq \
  git \
  build-essential \
  python3 \
  python3-venv \
  python3-pip

echo "=== Verifying Python and pip versions ==="
python3 --version
pip3 --version

ARCH=$(uname -m)
echo "=== Detected architecture: $ARCH ==="

if [[ "$ARCH" == "x86_64" ]]; then
  AWSCLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
elif [[ "$ARCH" == "aarch64" ]]; then
  AWSCLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi

echo "=== Installing AWS CLI v2 ==="
curl "$AWSCLI_URL" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

echo "=== Verifying AWS CLI version ==="
aws --version

echo "=== Cleanup AWS CLI installer ==="
rm -rf awscliv2.zip aws

echo "=== Setup Complete ==="
