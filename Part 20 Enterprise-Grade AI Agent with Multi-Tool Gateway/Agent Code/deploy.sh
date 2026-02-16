#!/bin/bash
# deploy.sh

set -e

# Configuration
ACCOUNT_ID="258652252690" # REPLACE WITH YOUR ACCOUNT ID
REGION="us-east-1" # REPLACE WITH YOUR REGION
REPO_NAME="sfoagent" # REPLACE WITH YOUR DESIRED REPO NAME

echo " Deploying Weather Agent Container (No Local Test)"
echo "================================================="

# Cleanup any existing containers
echo " Cleaning up existing containers..."
docker ps -aq --filter "name=sfoagent" | xargs -r docker rm -f 2>/dev/null || true

# Verify files exist
echo " Verifying files..."
for file in app.py Dockerfile requirements.txt; do
    if [[ ! -f "$file" ]]; then
        echo " Missing file: $file"
        exit 1
    else
        echo " Found: $file"
    fi
done

# Build container from scratch
echo " Building container from scratch..."
docker build --no-cache -t ${REPO_NAME}:latest .

# Create ECR repo if it doesn't exist
echo " Creating ECR repository..."
aws ecr create-repository \
  --repository-name ${REPO_NAME} \
  --region ${REGION} 2>/dev/null || echo "Repository already exists"

# Login to ECR
echo " Logging into ECR..."
aws ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Tag and push
echo " Pushing to ECR..."
docker tag ${REPO_NAME}:latest \
  ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest

docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest

echo "Container pushed to ECR!"
echo ""
echo "🔧 Next step: Configure your AgentCore Runtime with:"
echo "   Gateway URL: [Your actual gateway URL]"
echo "   OAuth Token: [Your actual OAuth token]"
echo ""