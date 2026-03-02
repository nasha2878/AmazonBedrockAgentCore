import os
import json
import logging
import sys
import base64
import re
import requests
import boto3
from flask import Flask, request, jsonify
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.services.identity import IdentityClient

# ----------------------------
# Initialization
# ----------------------------
agent = BedrockAgentCoreApp()
flask_app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")

GOOGLE_IDENTITY_NAME = os.environ.get("GOOGLE_IDENTITY_NAME")
GOOGLE_TOKENS_SECRET_ID = os.environ.get("GOOGLE_TOKENS_SECRET_ID")
AGENT_SECRET = os.environ.get("AGENT_SECRET")
GATEWAY_URL = os.environ.get("GATEWAY_URL")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
secrets = boto3.client("secretsmanager", region_name=AWS_REGION)

# ----------------------------
# Helper: Universal LLM Caller
# ----------------------------
def call_llm(messages):
    """Universal helper for Claude 4.5 Sonnet."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.2
    })
    resp = bedrock.invoke_model(modelId=MODEL_ID, body=body)
    data = json.loads(resp["body"].read())
    # Safely extract text from content list or object
    content = data.get("content", [])
    if isinstance(content, list) and content:
        return content[0].get("text", "")
    return content.get("text", "") if isinstance(content, dict) else ""

# ----------------------------
# Token Helpers (Cognito & Google)
# ----------------------------

def get_oauth_token():
    """Fetches Cognito JWT to authorize Gateway."""
    secret_value = secrets.get_secret_value(SecretId=AGENT_SECRET)
    secret = json.loads(secret_value["SecretString"])
    
    token_url = secret['DOMAIN'].rstrip("/") + "/oauth2/token"
    auth = base64.b64encode(f"{secret['CLIENT_ID']}:{secret['CLIENT_SECRET']}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials", "scope": secret.get("SCOPE", "")}

    response = requests.post(token_url, headers=headers, data=data, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]

def load_google_identity():
    """Resolves Google Client ID and Secret ARN from Bedrock AgentCore."""
    identity_client = IdentityClient(AWS_REGION)
    response = identity_client.cp_client.get_oauth2_credential_provider(name=GOOGLE_IDENTITY_NAME)
    
    config = response.get("oauth2ProviderConfigOutput", {}).get("googleOauth2ProviderConfig", {})
    client_id = config.get("clientId")
    
    secret_info = response.get("clientSecretArn", {})
    secret_arn = secret_info.get("secretArn")
    client_secret = None
    
    if secret_arn:
        s_resp = secrets.get_secret_value(SecretId=secret_arn)
        raw_val = s_resp.get("SecretString")
        try:
            s_json = json.loads(raw_val)
            client_secret = s_json.get("clientSecret") or s_json.get("client_secret") or raw_val
        except json.JSONDecodeError:
            client_secret = raw_val

    return {"client_id": client_id, "client_secret": client_secret}

def get_fresh_google_token():
    def log(msg):
        # sys.stderr + flush ensures the log prints before a crash
        print(f"DEBUG: {msg}", file=sys.stderr, flush=True)

    log("--- STARTING TOKEN REFRESH ---")
    
    try:
        # 1. Load your credentials
        resp = secrets.get_secret_value(SecretId=GOOGLE_TOKENS_SECRET_ID)
        tokens = json.loads(resp["SecretString"])
        cfg = load_google_identity()
        
        # 2. Build the payload
        data = {
            "client_id": cfg.get("client_id"),
            "client_secret": cfg.get("client_secret"),
            "refresh_token": tokens.get("refresh_token"),
            "grant_type": "refresh_token",
        }

        # DEBUG: Print exact payload content
        # Using repr() will show hidden characters like \n or spaces: 'abc ' vs 'abc'
        log(f"PAYLOAD client_id: {repr(data['client_id'])}")
        log(f"PAYLOAD client_secret: {repr(data['client_secret'])}")
        log(f"PAYLOAD refresh_token: {repr(data['refresh_token'])}")
        log(f"PAYLOAD grant_type: {repr(data['grant_type'])}")

        # 3. Request (URL MUST end in /token)
        target_url = "https://oauth2.googleapis.com/token"
        log(f"Sending POST to: {target_url}")
        
        token_resp = requests.post(
            target_url, 
            data=data, 
            timeout=30
        )
        
        # 4. Check for errors (401, 400, etc.)
        if token_resp.status_code != 200:
            log(f"!! GOOGLE REJECTED !! Status: {token_resp.status_code}")
            log(f"!! REASON: {token_resp.text}") # <--- This will show 'invalid_grant' if token is dead
            token_resp.raise_for_status()
        
        # 5. Success - Save new access token
        new_token = token_resp.json()["access_token"]
        log("Success! New token received.")
        
        tokens["access_token"] = new_token
        secrets.put_secret_value(SecretId=GOOGLE_TOKENS_SECRET_ID, SecretString=json.dumps(tokens))
        
        return new_token

    except Exception as e:
        log(f"CRITICAL ERROR: {str(e)}")
        raise

# ----------------------------
# Core Agent Logic
# ----------------------------

def run_agent(user_text: str):
    # 1. INTENT ROUTING: Search for PDF filename
    match = re.search(r'([A-Za-z0-9._-]+\.pdf)', user_text)
    
    # 2. CONVERSATIONAL FLOW: No PDF mentioned
    if not match:
        logger.info("No file requested. Providing conversational response.")
        prompt = f"Respond naturally as a helpful financial analyst to: '{user_text}'"
        return call_llm([{"role": "user", "content": [{"type": "text", "text": prompt}]}])

    # 3. TRANSACTIONAL FLOW: PDF detected
    file_name = match.group(1)
    logger.info(f"PDF detected: {file_name}. Initiating Identity flow.")

    gateway_jwt = get_oauth_token()
    google_token = get_fresh_google_token()

    target_tool = "myForecastAnalyst___myGoogleDriveTool" #REPLACE WITH YOUR TOOL NAME
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": target_tool,
            "arguments": {"file_name": file_name, "access_token": google_token}
        }
    }

    headers = {"Authorization": f"Bearer {gateway_jwt}", "Content-Type": "application/json"}
    resp = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    tool_resp = resp.json()

    # 4. Extract PDF and Analyze
    try:
        content_list = tool_resp.get("result", {}).get("content", [])
        pdf_b64 = None
        for item in content_list:
            if "file_base64" in item.get("text", ""):
                pdf_b64 = json.loads(item["text"])["file_base64"]
                break
        
        if not pdf_b64:
            return f"Error: Tool did not return PDF. Response: {tool_resp}"
        
        pdf_bytes = base64.b64decode(pdf_b64)
    except Exception as e:
        return f"Failed to parse tool output: {e}"

    # Multimodal Summary with Claude 4.5
    messages = [{
        "role": "user",
        "content": [
            {
                "type": "document", 
                "source": {
                    "type": "base64", 
                    "media_type": "application/pdf", 
                    "data": base64.b64encode(pdf_bytes).decode()
                }
            },
            {"type": "text", "text": f"Summarize this earnings PDF: {user_text}"}
        ]
    }]
    return call_llm(messages)

# ----------------------------
# Flask App Routes
# ----------------------------

@flask_app.route("/invocations", methods=["POST"])
def invocations():
    data = request.get_json() or {}
    user_input = data.get("input", {}).get("text", "")
    try:
        result = run_agent(user_input)
        return jsonify({"completion": result, "stop_reason": "end_turn"}), 200
    except Exception as e:
        logger.exception("Agent failed")
        return jsonify({"error": str(e)}), 500

@flask_app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=8080)
