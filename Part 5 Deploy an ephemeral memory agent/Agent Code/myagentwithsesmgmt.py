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

# Bedrock client for Titan Text Lite
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


@app.entrypoint
def invoke(payload):
    """
    Ephemeral conversational agent with Titan Text Lite.
    Session memory lasts only within runtime or session (e.g., 30 min – 30 days max).
    """

    # Parse payload
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    prompt = payload.get("prompt") or payload.get("input") or ""
    runtimeSessionId = payload.get("runtimeSessionId", "default-session")  # Corrected

    if not prompt:
        return {"message": "No prompt provided."}

    logger.info(f"Session: {runtimeSessionId}, Prompt: {prompt}")

    # Retrieve history for this session
    history = SESSION_MEMORY.get(runtimeSessionId, [])

    # Construct conversation prompt
    conversation = "\n".join([f"{m['role']}: {m['text']}" for m in history])
    full_prompt = f"{conversation}\nuser: {prompt}\nassistant:"

    # Invoke LLM (Amazon Titan Text Lite)
    try:
        response = bedrock.invoke_model(
            modelId="amazon.titan-text-lite-v1",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": full_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 256,
                    "temperature": 0.7,
                    "topP": 0.9
                }
            })
        )
        response_body = json.loads(response["body"].read())
        reply = response_body.get("results", [{}])[0].get("outputText", "")
    except Exception as e:
        logger.exception("Error calling Titan Text Lite:")
        reply = f"Error: {str(e)}"

    # Update ephemeral session memory
    history.append({"role": "user", "text": prompt})
    history.append({"role": "assistant", "text": reply})
    SESSION_MEMORY[runtimeSessionId] = history[-10:]  # Keep only the last 10 exchanges to limit token usage

    return {"message": reply}


if __name__ == "__main__":
    app.run()
