# myllmagent.py
import json
import logging
import boto3
from bedrock_agentcore import BedrockAgentCoreApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the agentcore app
app = BedrockAgentCoreApp()

# Initialize Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Replace with your deployed model ID
MODEL_ID = "amazon.titan-text-lite-v1"

@app.entrypoint
def invoke(payload):
    """
    payload: dict from agentcore CLI, e.g. {"prompt": "..."}
    Returns JSON-serializable dict with key "message"
    """
    # Handle bytes/string payload
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    # Extract prompt
    prompt = payload.get("prompt") or payload.get("input") or ""
    logger.info("Received prompt: %s", prompt)

    if not prompt:
        return {"message": "No prompt provided."}

    # Prepare request for Bedrock Titan model
    try:
        request_body = json.dumps({"inputText": prompt}).encode("utf-8")
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=request_body,
            contentType="application/json",
            accept="application/json"
        )

        # Read response
        response_body = response['body'].read()
        model_output = json.loads(response_body)
        logger.info("Model output: %s", model_output)

        # Return the message key
        return {"message": model_output.get("outputText", str(model_output))}

    except Exception as e:
        logger.error("Error calling LLM: %s", e, exc_info=True)
        return {"message": f"Error calling LLM: {e}"}


if __name__ == "__main__":
    app.run()
