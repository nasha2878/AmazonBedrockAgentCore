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

# Initialize Bedrock AgentCore app
app = BedrockAgentCoreApp()

# Configuration constants
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
MEMORY_ID = "memory_76xv1-pn5F0eAgFq"   # <-- YOUR MEMORY ID
SESSION_ID = "default_session"

S3_BUCKET = "mysmslabbucket" # <-- YOUR SE BUCKET NAME
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:258652252690:mysmslabtopic" # <-- YOUR SNS TOPIC ARN

# --- Lazy client getters ---
def get_memory_client():
    return MemoryClient(region_name="us-east-1")

def get_s3():
    return boto3.client("s3", region_name="us-east-1")

def get_sns():
    return boto3.client("sns", region_name="us-east-1")

def get_bedrock():
    return boto3.client("bedrock-runtime", region_name="us-east-1")

# --- Helper: publish to SNS ---
def publish_to_sns(payload: dict):
    try:
        sns = get_sns()
        sns.publish(TopicArn=SNS_TOPIC_ARN, Message=json.dumps(payload))
        logger.info(f"Published message to SNS: {payload}")
    except Exception as e:
        logger.error(f"Failed to publish to SNS: {e}", exc_info=True)

# --- STM Helpers ---
def add_event(actor_id, content):
    role = actor_id.upper()
    memory_client = get_memory_client()
    s3 = get_s3()

    try:
        response = memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=role,
            session_id=SESSION_ID,
            event_timestamp=datetime.now(timezone.utc),
            messages=[(str(content), role)]
        )
        event = response.get("event", {})
        logger.info(f"Created STM event: {event.get('eventId', 'unknown')}")

        payload = {
            "actor": role,
            "text": str(content),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        key = f"{SESSION_ID}/{uuid.uuid4()}.json"

        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(payload))
        logger.info(f"Stored durable fact in S3: {key}")

        publish_to_sns(payload)
        return response
    except Exception as e:
        logger.error(f"Failed to create STM event: {e}", exc_info=True)
        return {}

def reset_memory():
    memory_client = get_memory_client()
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
                if event_id:
                    memory_client.delete_event(
                        memoryId=MEMORY_ID,
                        sessionId=SESSION_ID,
                        eventId=event_id,
                        actorId=actor
                    )
            logger.info(f"Deleted {len(events)} events for {actor}.")
        except Exception as e:
            logger.error(f"Error resetting memory for {actor}: {e}", exc_info=True)

    logger.info("Memory reset complete.")

def hydrate_context_from_s3():
    s3 = get_s3()
    try:
        objects = s3.list_objects_v2(Bucket=S3_BUCKET).get("Contents", [])
        snippets = []
        for obj in objects:
            body = s3.get_object(Bucket=S3_BUCKET, Key=obj["Key"])["Body"].read()
            try:
                payload = json.loads(body)
                snippets.append(payload.get("text", str(payload)))
            except Exception:
                snippets.append(body.decode("utf-8"))
        logger.info(f"Hydrated {len(snippets)} facts from S3")
        return "\n".join(snippets)
    except Exception as e:
        logger.error(f"Failed to hydrate context from S3: {e}", exc_info=True)
        return ""

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

    if user_input.strip().lower() == "reset":
        reset_memory()
        durable_context = hydrate_context_from_s3()
        return {"message": f"Memory reset. Durable context loaded:\n{durable_context}"}

    add_event("USER", user_input)

    memory_client = get_memory_client()
    events = memory_client.list_events(
        memory_id=MEMORY_ID,
        actor_id="USER",
        session_id=SESSION_ID,
        include_payload=True,
        max_results=50
    )

    merged_messages = [{"role": "user", "content": user_input}]
    if events:
        logger.info(f"Retrieved {len(events)} STM events for USER")

    durable_context = hydrate_context_from_s3()
    system_prompt = (
        "You are a helpful assistant. Use prior messages for context and respond only to the last user message.\n\n"
        f"Durable facts:\n{durable_context}"
    )

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "system": system_prompt,
        "messages": merged_messages,
        "max_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.9
    }

    bedrock = get_bedrock()
    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(request_body).encode("utf-8"),
            contentType="application/json",
            accept="application/json"
        )
        result_body = response["body"].read()
        result = json.loads(result_body)
        assistant_text = result.get("content", [{}])[0].get("text", "")

        add_event("ASSISTANT", assistant_text)
        return {"message": assistant_text}
    except Exception as e:
        logger.error(f"Error calling Claude: {e}", exc_info=True)
        return {"message": f"Error calling Claude: {e}"}

if __name__ == "__main__":
    app.run()
