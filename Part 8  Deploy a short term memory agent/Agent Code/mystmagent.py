import os
import json
import logging
import boto3
from colorama import init, Fore, Style
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

# Initialize colorama
init(autoreset=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock AgentCore app and clients
app = BedrockAgentCoreApp()
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
memory_client = MemoryClient(region_name="us-east-1")

# Configuration constants
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
MEMORY_ID = "mystmmemory-otBM7C6wjc" #REPLACE WITH YOUR MEMORY ID
SESSION_ID = "default_session"

def add_event(actor_id, content):
    role = actor_id.upper()
    text = str(content)
    messages = [(text, role)]

    try:
        response = memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=role,
            session_id=SESSION_ID,
            messages=messages
        )
        logger.info(Fore.MAGENTA + f"Created event: {response.get('eventId', 'unknown')}")
        return response
    except Exception as e:
        logger.error(Fore.RED + f"Failed to create event: {e}", exc_info=True)
        return {}

def reset_memory():
    for actor in ["USER", "ASSISTANT"]:
        events = memory_client.list_events(
            memory_id=MEMORY_ID,
            actor_id=actor,
            session_id=SESSION_ID,
            include_payload=False,
            max_results=100
        )
        for e in events:
            memory_client.delete_event(
                memoryId=MEMORY_ID,
                sessionId=SESSION_ID,
                eventId=e["eventId"],
                actorId=actor
            )
    logger.info(Fore.CYAN + "Memory reset complete.")

@app.entrypoint
def invoke(payload):
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    user_input = payload.get("prompt") or payload.get("input") or ""
    if not user_input:
        return {"message": "No prompt provided."}

    if user_input.strip().lower() == "reset":
        reset_memory()
        return {"message": "Memory reset. Let's start fresh!"}

    add_event("USER", user_input)

    events = memory_client.list_events(
        memory_id=MEMORY_ID,
        actor_id="USER",
        session_id=SESSION_ID,
        include_payload=True,
        max_results=50
    )

    merged_messages = []
    last_user_message = None
    last_role = None
    buffer = []

    for e in events:
        for m in e.get("payload", []):
            msg = m.get("conversational", {})
            role = msg.get("role", "UNKNOWN").lower()
            content = msg.get("content", {}).get("text", "")
            if role not in {"user", "assistant"}:
                continue
            if role == "user":
                last_user_message = content
            if role != last_role and buffer:
                merged_messages.append({
                    "role": last_role,
                    "content": "\n".join(buffer)
                })
                buffer = []
            buffer.append(content)
            last_role = role

    if buffer and last_role:
        merged_messages.append({
            "role": last_role,
            "content": "\n".join(buffer)
        })

    # Ensure last message is from user to maintain alternation
    if merged_messages and merged_messages[-1]["role"] == "user":
        merged_messages.append({"role": "assistant", "content": ""})

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "system": "You are a helpful assistant. Use all prior messages for context and respond only to the last user message. Don't respond to the previous messages.",
        "messages": merged_messages,
        "max_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.9
    }

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(request_body).encode("utf-8"),
            contentType="application/json",
            accept="application/json"
        )
        result_body = response["body"].read()
        result = json.loads(result_body)
        assistant_text = result.get("content", str(result))

        add_event("ASSISTANT", assistant_text)

        return {"message": assistant_text}
    except Exception as e:
        logger.error(Fore.RED + f"Error calling Claude: {e}", exc_info=True)
        return {"message": f"Error calling Claude: {e}"}

if __name__ == "__main__":
    app.run()
