# myagent.py
import json
import logging
from bedrock_agentcore import BedrockAgentCoreApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AgentCore app
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """
    payload is a dict (agentcore CLI sends {"prompt": "..."}).
    Return a JSON-serializable dict with key "message".
    """
    # Defensive payload parsing
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    prompt = payload.get("prompt") or payload.get("input") or ""
    logger.info("Received prompt: %s", prompt)

    if not prompt:
        return {"message": "No prompt provided."}

    # Simple response logic
    if "joke" in prompt.lower():
        reply = "Why did the developer go broke? Because he used up all his cache."
    elif "name" in prompt.lower():
        reply = "I remember you said your name is Namrata."
    else:
        reply = f"You said: {prompt}"

    logger.info("Replying: %s", reply)
    return {"message": reply}

if __name__ == "__main__":
    app.run()
