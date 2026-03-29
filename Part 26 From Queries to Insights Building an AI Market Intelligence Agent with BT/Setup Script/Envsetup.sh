#!/bin/bash
# ==========================================
# System Setup: Ubuntu + AWS CLI + Docker
# ==========================================

set -e
set -o pipefail

echo "=== Updating system ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installing core utilities ==="
sudo apt install -y \
  ca-certificates \
  curl \
  unzip \
  jq \
  git \
  gnupg \
  lsb-release \
  build-essential \
  python3 \
  python3-venv \
  python3-pip

echo "=== Verifying Python ==="
python3 --version
pip3 --version

echo "=== Installing AWS CLI v2 ==="
ARCH=$(uname -m)

if [ "$ARCH" = "aarch64" ]; then
    AWS_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"
else
    AWS_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
fi

curl "$AWS_URL" -o awscliv2.zip
unzip awscliv2.zip
sudo ./aws/install
rm -rf awscliv2.zip aws

echo "=== AWS CLI Version ==="
aws --version

echo "=== Installing Docker ==="
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

echo "=== Setting up Docker Buildx ==="
docker buildx create --name arm-builder --use || true
docker buildx inspect --bootstrap || true

echo "=== System Setup Complete ==="
echo "Log out and log back in before using Docker without sudo."
