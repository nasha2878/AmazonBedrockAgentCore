# myagent_with_memory.py
import json
import logging
import boto3
from bedrock_agentcore import BedrockAgentCoreApp

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = BedrockAgentCoreApp()

# Ephemeral (in-memory) session memory
SESSION_MEMORY = {}

# Bedrock client for Claude 3 Haiku
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


@app.entrypoint
def invoke(payload):
    """
    Ephemeral conversational agent using Claude 3 Haiku via Bedrock.
    Session memory lasts only within the current runtime.
    """

    # Parse payload safely
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    prompt = payload.get("prompt") or payload.get("input") or ""
    runtimeSessionId = payload.get("runtimeSessionId", "default-session")

    if not prompt:
        return {"message": "No prompt provided."}

    logger.info(f"Session: {runtimeSessionId}, Prompt: {prompt}")

    # Retrieve short-term conversation history
    history = SESSION_MEMORY.get(runtimeSessionId, [])

    # Format conversation as chat messages for Claude
    messages = []
    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": [{"type": "text", "text": m["text"]}]})

    # Append new user input
    messages.append({"role": "user", "content": [{"type": "text", "text": prompt}]})

    # Construct the Claude request payload
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0.7,
        "messages": messages
    }

    # Call Claude 3 Haiku
    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        response_body = json.loads(response["body"].read())
        reply = response_body.get("content", [{}])[0].get("text", "")
    except Exception as e:
        logger.exception("Error calling Claude 3 Haiku:")
        reply = f"Error: {str(e)}"

    # Update ephemeral session memory (limit to last 10 turns)
    history.append({"role": "user", "text": prompt})
    history.append({"role": "assistant", "text": reply})
    SESSION_MEMORY[runtimeSessionId] = history[-10:]  # keep last 10 exchanges only

    return {"message": reply}


if __name__ == "__main__":
    app.run()
