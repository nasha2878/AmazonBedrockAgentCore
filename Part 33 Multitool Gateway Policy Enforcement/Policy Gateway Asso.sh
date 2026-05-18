#!/bin/bash

# Define targeted resource IDs matching your exact environment deployment
ROLE_NAME="<<YOUR AGENTCORE GATEWAY ROLE NAME>>" 
GATEWAY_ID="<<YOUR AGENTCORE GATEWAY ID>>"
POLICY_ENGINE_ARN="<<YOUR POLICY ENGINE ARN>>"
REGION="us-east-1"

echo "Step 1: Generating the admin-level wildcard inline policy document..."
cat << 'EOF' > admin-fix.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BypassCheckAuthorizePermissionsBug",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:*",
                "bedrock-agentcore-control:*"
            ],
            "Resource": "*"
        }
    ]
}
EOF

echo "Step 2: Injecting the permission patch policy directly to your active role: ${ROLE_NAME}..."
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "AdminBugFixOverride" \
    --policy-document file://admin-fix.json \
    --region "$REGION"

echo "Step 3: Fetching a clean tracking copy of the current active gateway payload object..."
aws bedrock-agentcore-control get-gateway \
    --gateway-identifier "$GATEWAY_ID" \
    --region "$REGION" > current_gw.json

echo "Step 4: Parsing structural config parameters using jq utilities..."
GW_NAME=$(jq -r '.name' current_gw.json)
GW_ROLE=$(jq -r '.roleArn' current_gw.json)
GW_AUTH=$(jq -r '.authorizerType' current_gw.json)
GW_AUTH_CONFIG=$(jq -c '.authorizerConfiguration' current_gw.json)

echo "Step 5: Executing the full-replacement Control Plane API payload update to switch to ENFORCE mode..."
aws bedrock-agentcore-control update-gateway \
    --gateway-identifier "$GATEWAY_ID" \
    --name "$GW_NAME" \
    --role-arn "$GW_ROLE" \
    --authorizer-type "$GW_AUTH" \
    --authorizer-configuration "$GW_AUTH_CONFIG" \
    --policy-engine-configuration "{\"arn\":\"${POLICY_ENGINE_ARN}\",\"mode\":\"ENFORCE\"}" \
    --region "$REGION"

echo "Cleanup: Removing local workspace execution JSON configuration files..."
rm -f admin-fix.json current_gw.json

echo "Complete! Your AgentCore Gateway is now updating its runtime parameters to active enforcement state."
