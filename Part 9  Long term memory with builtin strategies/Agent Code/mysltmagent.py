import os
import json
import logging
import boto3
import uuid
from datetime import datetime, timezone
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

# Configuration constants
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
MEMORY_ID = "memltm-7CYKwqCwxE" # REPLACE WITH YOUR MEMORY ID
SESSION_ID = "default_session"

# Memory client bound to your memory resource
memory_client = MemoryClient(region_name="us-east-1")

# --- Namespace constants ---
PREFERENCE_NS = "/strategies/preference_builtin_hb1v7-46DQnh5IJL/actors/USER" #REPLACE "preference_builtin_3hcz2-jAuQfKDzB0" WITH YOUR STRATEGY ID
SEMANTIC_NS   = "/strategies/semantic_builtin_hb1v7-AKq1z38jrm/actors/USER" #REPLACE "semantic_builtin_3hcz2-TZeuvU4QcD/" WITH YOUR STRATEGY ID
SUMMARY_BASE  = "/strategies/summary_builtin_hb1v7-oFrUjhFNJW/actors/USER/sessions" #REPLACE "summary_builtin_3hcz2-eDyoXs6cO1" WITH YOUR STRATEGY ID

# --- STM Helpers ---
def add_event(actor_id, content):
    """Add an event to STM with timestamp for consistency."""
    role = actor_id.upper()
    try:
        response = memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=role,
            session_id=SESSION_ID,
            event_timestamp=datetime.now(timezone.utc),
            messages=[(str(content), role)]
        )
        event = response.get("event", {})
        logger.info(Fore.MAGENTA + f"Created event: {event.get('eventId', 'unknown')}")
        return response
    except Exception as e:
        logger.error(Fore.RED + f"Failed to create event: {e}", exc_info=True)
        return {}

def reset_memory():
    """Delete all STM events for USER and ASSISTANT safely."""
    for actor in ["USER", "ASSISTANT"]:
        try:
            events = memory_client.list_events(
                memory_id=MEMORY_ID,
                actor_id=actor,
                session_id=SESSION_ID,
                include_payload=False,
                max_results=100
            )
            for e in events:
                event_id = e.get("eventId")
                if not event_id:
                    continue
                memory_client.delete_event(
                    memoryId=MEMORY_ID,
                    sessionId=SESSION_ID,
                    eventId=event_id,
                    actorId=actor
                )
            logger.info(Fore.CYAN + f"Deleted {len(events)} events for {actor}.")
        except Exception as e:
            logger.error(Fore.RED + f"Error resetting memory for {actor}: {e}", exc_info=True)

    logger.info(Fore.CYAN + "Memory reset complete.")

# --- Hydrate durable facts including summarization ---
def hydrate_context(session_id=SESSION_ID):
    """Retrieve durable facts from preference, semantic, and summarization namespaces."""
    pref_facts = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=PREFERENCE_NS,
        query="*"
    )
    sem_facts = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=SEMANTIC_NS,
        query="*"
    )
    summary_ns = f"{SUMMARY_BASE}/{session_id}"
    sum_facts = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=summary_ns,
        query="*"
    )

    context_snippets = []
    for f in pref_facts + sem_facts + sum_facts:
        text = f["content"]["text"]
        context_snippets.append(text)

    return "\n".join(context_snippets)

# --- Entrypoint ---
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

    # Special commands
    tokens = user_input.strip().lower().split()
    cmd = tokens[0] if tokens else ""

    if cmd == "reset":
        reset_memory()
        durable_context = hydrate_context(session_id=SESSION_ID)
        return {"message": f"Memory reset. Durable context loaded:\n{durable_context}"}

    # Add user event to STM
    add_event("USER", user_input)

    # Retrieve STM events
    events = memory_client.list_events(
        memory_id=MEMORY_ID,
        actor_id="USER",
        session_id=SESSION_ID,
        include_payload=True,
        max_results=50
    )

    merged_messages = []
    last_role = None
    buffer = []

    for e in events:
        for m in e.get("payload", []):
            msg = m.get("conversational", {})
            role = msg.get("role", "UNKNOWN").lower()
            content = msg.get("content", {}).get("text", "")
            if role not in {"user", "assistant"}:
                continue
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

    if merged_messages and merged_messages[-1]["role"] == "user":
        merged_messages.append({"role": "assistant", "content": ""})

    if not merged_messages:
        merged_messages = [{"role": "user", "content": user_input}]

    # --- Inject durable facts into system prompt ---
    durable_context = hydrate_context(session_id=SESSION_ID)
    system_prompt = f"You are a helpful assistant. Use prior messages for context and respond only to the last user message.\n\nDurable facts:\n{durable_context}"

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "system": system_prompt,
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
        assistant_text = ""

        if "content" in result and result["content"]:
            if isinstance(result["content"], list):
                assistant_text = result["content"][0].get("text", "")
            else:
                assistant_text = str(result["content"])
        else:
            assistant_text = json.dumps(result)

        add_event("ASSISTANT", assistant_text)
        return {"message": assistant_text}

    except Exception as e:
        logger.error(Fore.RED + f"Error calling Claude: {e}", exc_info=True)
        return {"message": f"Error calling Claude: {e}"}

if __name__ == "__main__":
    app.run()
