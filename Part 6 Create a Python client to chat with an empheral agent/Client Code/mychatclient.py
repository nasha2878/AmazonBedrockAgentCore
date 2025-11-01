import boto3
import json
import uuid

# --- Config ---
REGION = "us-east-1"
AGENT_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:XXXX:runtime/myagentwithsesmgmt-hpSWuS6Akm"  # <-- replace with your runtime ARN

# --- Create Bedrock AgentCore client ---
client = boto3.client("bedrock-agentcore", region_name=REGION)

# --- Generate a session ID (so the agent remembers context) ---
runtime_session_id = "session-" + str(uuid.uuid4()).replace("-", "")[:33]

print(f"Starting chat session: {runtime_session_id}")
print("Type 'exit' to end the chat.\n")

def invoke_agent(prompt: str):
    """Invoke Bedrock AgentCore runtime with conversational context."""
    payload = {
        "prompt": prompt
    }

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=runtime_session_id,
        payload=json.dumps(payload),
        qualifier="DEFAULT"
    )

    response_body = response["response"].read()
    response_data = json.loads(response_body)
    message = response_data.get("message", "")
    print(f"Agent: {message}")
    return message


# --- Chat loop ---
if __name__ == "__main__":
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Ending session.")
            break

        try:
            invoke_agent(user_input)
        except Exception as e:
            print(f"Error: {e}")
