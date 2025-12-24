import os
import json
import logging
import boto3
import uuid
from datetime import datetime, timezone
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock AgentCore app and clients
app = BedrockAgentCoreApp()
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Configuration constants
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
MEMORY_ID = "memory_c2twc-GEY9XWG6GL"  # REPLACE memory_c2twc-GEY9XWG6GL WITH YOUR MEMORY ID
SESSION_ID = "default_session"

# Memory client bound to your memory resource
memory_client = MemoryClient(region_name="us-east-1")

# --- Namespace constants (durable strategies) ---

# Preference & semantic & summary (already present)
PREFERENCE_NS = "/strategies/preference_builtin_c2twc-k5RSVyFfdj/actors/USER"  # REPLACE preference_builtin_c2twc-k5RSVyFfdj WITH YOUR STRATEGY ID
SEMANTIC_NS   = "/strategies/semantic_builtin_c2twc-uF5xxZF6p1/actors/USER"    # REPLACE semantic_builtin_c2twc-uF5xxZF6p1 WITH YOUR STRATEGY ID
SUMMARY_BASE  = "/strategies/summary_builtin_c2twc-Sdj72kDyfH/actors/USER/sessions"  # REPLACE summary_builtin_c2twc-Sdj72kDyfH WITH YOUR STRATEGY ID

# ADD EPISODIC MEMORY
# Extraction (episodes) are session-scoped
EPISODIC_EPISODES_BASE_NS   = "/strategies/episodic_builtin_c2twc-WckB6cExjW/actors/USER/sessions" # REPLACE episodic_builtin_c2twc-WckB6cExjW WITH YOUR STRATEGY ID
# Reflections are actor-scoped
EPISODIC_REFLECTION_NS      = "/strategies/episodic_builtin_c2twc-WckB6cExjW/actors/USER" # REPLACE episodic_builtin_c2twc-WckB6cExjW WITH YOUR STRATEGY ID


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
        logger.info(f"Created event: {event.get('eventId', 'unknown')}")
        return response
    except Exception as e:
        logger.error(f"Failed to create event: {e}", exc_info=True)
        return {}


def reset_memory():
    """Delete all STM events for USER and ASSISTANT safely.
    Does NOT touch durable memories (preference/semantic/episodic/summary).
    """
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
            logger.info(f"Deleted {len(events)} events for {actor}.")
        except Exception as e:
            logger.error(f"Error resetting memory for {actor}: {e}", exc_info=True)

    logger.info("STM memory reset complete.")


# --- Episodic helpers (optional, if you want explicit writes) ---

def write_episode(text, session_id=SESSION_ID):
    """Optionally store a structured episode in the episodic extraction namespace."""
    try:
        ns = f"{EPISODIC_EPISODES_BASE_NS}/{session_id}"
        memory_client.store_memory(
            memory_id=MEMORY_ID,
            namespace=ns,
            content={"text": text}
        )
        logger.info(f"Episodic episode stored in {ns}.")
    except Exception as e:
        logger.error(f"Failed to store episodic episode: {e}", exc_info=True)


def write_reflection(text):
    """Optionally store an explicit reflection in the episodic reflection namespace."""
    try:
        memory_client.store_memory(
            memory_id=MEMORY_ID,
            namespace=EPISODIC_REFLECTION_NS,
            content={"text": text}
        )
        logger.info("Episodic reflection stored.")
    except Exception as e:
        logger.error(f"Failed to store episodic reflection: {e}", exc_info=True)


# --- Hydrate durable facts including episodic & summarization ---

def hydrate_context(session_id=SESSION_ID):
    """Retrieve durable facts from preference, semantic, episodic (episodes + reflections), and summarization namespaces."""
    # Preferences
    pref_facts = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=PREFERENCE_NS,
        query="*"
    )

    # Long-term semantic facts
    sem_facts = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=SEMANTIC_NS,
        query="*"
    )

    # Episodic episodes (session-scoped)
    epi_episode_ns = f"{EPISODIC_EPISODES_BASE_NS}/{session_id}"
    epi_episodes = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=epi_episode_ns,
        query="*"
    )

    # Episodic reflections (actor-scoped, cross-session insights)
    epi_reflections = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=EPISODIC_REFLECTION_NS,
        query="*"
    )

    # Summaries (session-scoped)
    summary_ns = f"{SUMMARY_BASE}/{session_id}"
    sum_facts = memory_client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=summary_ns,
        query="*"
    )

    context_snippets = []
    for f in pref_facts + sem_facts + epi_episodes + epi_reflections + sum_facts:
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
        return {"message": f"STM reset. Durable context (preferences, semantic, episodic, summaries) remains:\n{durable_context}"}

    # Add user event to STM
    add_event("USER", user_input)

    # Retrieve STM events (USER)
    events = memory_client.list_events(
        memory_id=MEMORY_ID,
        actor_id="USER",
        session_id=SESSION_ID,
        include_payload=True,
        max_results=50
    )

    # Merge STM messages into a conversational history
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

    # Ensure last message is user; add assistant stub if needed
    if merged_messages and merged_messages[-1]["role"] == "user":
        merged_messages.append({"role": "assistant", "content": ""})

    # Fallback if no STM messages retrieved
    if not merged_messages:
        merged_messages = [{"role": "user", "content": user_input}]

    # --- Inject durable facts (including episodic) into system prompt ---
    durable_context = hydrate_context(session_id=SESSION_ID)
    system_prompt = (
        "You are a helpful assistant. Use prior messages for context and respond only to the last user message.\n\n"
        "Durable facts (preferences, semantic knowledge, episodic episodes & reflections, summaries):\n"
        f"{durable_context}"
    )

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

        # Add assistant reply to STM
        add_event("ASSISTANT", assistant_text)

        return {"message": assistant_text}

    except Exception as e:
        logger.error(f"Error calling Claude: {e}", exc_info=True)
        return {"message": f"Error calling Claude: {e}"}


if __name__ == "__main__":
    app.run()
