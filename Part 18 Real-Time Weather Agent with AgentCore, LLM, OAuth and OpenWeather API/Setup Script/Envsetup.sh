#!/bin/bash
# =============================================
# Setup Script: Ubuntu Core Utilities, Python 3.12, AWS CLI v2, Docker (ARM64)
# =============================================

set -e  # Exit on any error
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
  build-essential

echo "=== Installing Python 3, venv, and pip ==="
sudo apt install -y python3 python3-venv python3-pip

echo "=== Verifying Python and pip versions ==="
python3 --version
pip3 --version

echo "=== Installing AWS CLI v2 (ARM64) ==="
curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o awscliv2.zip
unzip awscliv2.zip
sudo ./aws/install

echo "=== Verifying AWS CLI version ==="
aws --version

echo "=== Cleanup AWS CLI installer ==="
rm -rf awscliv2.zip aws

echo "=== Installing and enabling Docker (ARM64) ==="
curl -fsSL https://get.docker.com | sudo sh

echo "=== Adding current user to Docker group ==="
sudo usermod -aG docker $USER
newgrp docker

echo "=== Verifying Docker installation ==="
docker version

echo "=== Setting up Docker Buildx for multi-arch ==="
docker buildx create --name arm-builder --use
docker buildx inspect --bootstrap
docker buildx inspect | grep Platforms

echo "=== Setup Complete ==="
