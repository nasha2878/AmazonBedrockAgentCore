import boto3
import json

AGENT_RUNTIME_ARN = "<<AGENT ARN>>"  # REPLACE WITH AGENT'S ARN
REGION = "us-east-1" #REPLACE WITH YOUR REGION

client = boto3.client("bedrock-agentcore", region_name=REGION)

def invoke_agent(message: str):
    payload = {
        "input": {"text": message}
    }

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            payload=json.dumps(payload).encode("utf-8"),
            contentType="application/json"
        )

        if "response" in response:
            body = response["response"]
            data = body.read() if hasattr(body, "read") else body
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            try:
                parsed = json.loads(data)
                for key in ["completion", "output", "result", "response", "text", "message"]:
                    if key in parsed:
                        return parsed[key]
                return parsed
            except json.JSONDecodeError:
                return data
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("AgentCore Client - Enter a prompt (type 'exit' to quit)")
    while True:
        msg = input("You: ").strip()
        if msg.lower() in ["exit", "quit"]:
            break
        if not msg:
            continue
        resp = invoke_agent(msg)
        print(f"Agent Response: {resp}\n")

if __name__ == "__main__":
    main()

