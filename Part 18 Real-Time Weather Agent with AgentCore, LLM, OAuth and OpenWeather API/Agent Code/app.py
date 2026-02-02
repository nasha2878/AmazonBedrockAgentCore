import os
import json
import logging
import base64
import requests
import boto3
from flask import Flask, request, jsonify
from bedrock_agentcore import BedrockAgentCoreApp
from botocore.exceptions import ClientError

# -----------------------------
# Setup Flask + logging
# -----------------------------
flask_app = Flask(__name__)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# -----------------------------
# AgentCore + AWS clients
# -----------------------------
agent = BedrockAgentCoreApp()   # REQUIRED for AgentCore runtime
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
secrets = boto3.client("secretsmanager", region_name=AWS_REGION)

# -----------------------------
# Configuration (ENV)
# -----------------------------
GATEWAY_URL = os.environ.get("GATEWAY_URL")
WEATHER_AGENT_SECRET = os.environ.get("WEATHER_AGENT_SECRET")

MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

# -----------------------------
# Fetch OAuth token dynamically
# -----------------------------
def get_oauth_token():
    try:
        secret_value = secrets.get_secret_value(
            SecretId=WEATHER_AGENT_SECRET
        )
        secret = json.loads(secret_value["SecretString"])

        client_id = secret["CLIENT_ID"]
        client_secret = secret["CLIENT_SECRET"]
        token_url = secret["TOKEN_URL"]
        scope = secret["SCOPE"]

        auth = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "client_credentials",
            "scope": scope
        }

        response = requests.post(token_url, headers=headers, data=data, timeout=30)
        response.raise_for_status()

        return response.json()["access_token"]

    except Exception as e:
        logger.error(f"Failed to fetch OAuth token: {e}")
        raise

# -----------------------------
# Fetch tools dynamically
# -----------------------------
def get_gateway_weather_tool(token):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    tools = result.get("result", {}).get("tools", [])

    for tool in tools:
        if "weather" in tool.get("name", "").lower():
            return tool["name"]

    raise RuntimeError("No weather tool found in Gateway")

# -----------------------------
# Call Gateway weather tool
# -----------------------------
def call_weather_tool(token, tool_name, city):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": {"city": city}
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

# -----------------------------
# Call Bedrock Claude Sonnet
# -----------------------------
def call_llm(prompt):
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.5
    }

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(request_body).encode("utf-8"),
        contentType="application/json",
        accept="application/json"
    )

    body = json.loads(response["body"].read())

    # Claude may return list or string
    content = body.get("content", "")
    if isinstance(content, list):
        return content[0].get("text", "")
    return content

# -----------------------------
# Main invocation endpoint
# -----------------------------
@flask_app.route("/invocations", methods=["POST"])
def invocations():
    try:
        payload = json.loads(request.data.decode("utf-8"))
        user_text = payload.get("input", {}).get("text", "")

        token = get_oauth_token()
        weather_tool = get_gateway_weather_tool(token)

        # Step 1: Ask LLM what to do
        decision_prompt = f"""
You are an AI agent.

If the user is asking about weather (current or future), respond ONLY with JSON:
{{"action":"weather","city":"CITY_NAME"}}

Otherwise respond with:
{{"action":"answer"}}

User input:
{user_text}
"""

        decision_raw = call_llm(decision_prompt)
        decision_raw = decision_raw.strip()

        try:
            decision = json.loads(decision_raw)
        except json.JSONDecodeError:
            decision = {"action": "answer"}

        # Step 2: Weather path
        if decision.get("action") == "weather":
            city = decision.get("city", "New York City")

            weather_data = call_weather_tool(token, weather_tool, city)

            final_prompt = f"""
Weather data:
{json.dumps(weather_data, indent=2)}

User question:
{user_text}

Respond clearly and naturally.
"""
            answer = call_llm(final_prompt)

        # Step 3: General LLM answer
        else:
            answer = call_llm(user_text)

        return jsonify({
            "completion": answer,
            "stop_reason": "end_turn"
        }), 200

    except Exception as e:
        logger.exception("Invocation failed")
        return jsonify({
            "completion": f"Error: {str(e)}",
            "stop_reason": "end_turn"
        }), 200

# -----------------------------
# Health endpoints
# -----------------------------
@flask_app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

# -----------------------------
# Run app
# -----------------------------
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=8080, debug=True)
