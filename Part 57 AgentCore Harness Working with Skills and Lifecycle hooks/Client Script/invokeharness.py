
import boto3
import uuid
import re
from urllib.parse import quote

# --------------------------------------------------
# Configuration
# --------------------------------------------------

REGION = "<< YOUR REGION >>"

HARNESS_ARN = (
    "<< YOUR HARNESS ARN >>"
)

QUALIFIER = "DEFAULT"

# --------------------------------------------------
# AWS Clients
# --------------------------------------------------

sts = boto3.client("sts", region_name=REGION)

agentcore = boto3.client(
    "bedrock-agentcore",
    region_name=REGION
)

# --------------------------------------------------
# Caller Identity
# --------------------------------------------------

caller = sts.get_caller_identity()

user_id = caller["UserId"]
user_arn = caller["Arn"]

runtime_user_id = user_id

# --------------------------------------------------
# Session and Identity Propagation
# --------------------------------------------------

session_id = str(uuid.uuid4())

baggage = (
    f"user.id={quote(user_id, safe='')},"
    f"user.arn={quote(user_arn, safe='')}"
)

# --------------------------------------------------
# User Request
# --------------------------------------------------

prompt = input("\nEnter your request: ").strip()

if not prompt:
    raise ValueError("Request cannot be empty.")

print("\nInvoking governance harness...")
print(f"Session ID: {session_id}")
print(f"Authenticated User: {user_arn}")

# --------------------------------------------------
# Invoke Harness
# --------------------------------------------------

response = agentcore.invoke_harness(
    harnessArn=HARNESS_ARN,
    qualifier=QUALIFIER,
    runtimeSessionId=session_id,
    runtimeUserId=runtime_user_id,
    baggage=baggage,
    messages=[
        {
            "role": "user",
            "content": [
                {"text": prompt}
            ]
        }
    ]
)

# --------------------------------------------------
# Process Streaming Response
# --------------------------------------------------

response_text = []

for event in response.get("stream", []):

    content_delta = event.get("contentBlockDelta", {})
    delta = content_delta.get("delta", {})

    text_chunk = delta.get("text")

    if isinstance(text_chunk, str):
        response_text.append(text_chunk)

# --------------------------------------------------
# Assemble and Clean Response
# --------------------------------------------------

full_response = "".join(response_text)

# Remove thinking blocks from the assembled response
full_response = re.sub(
    r"<thinking>.*?</thinking>",
    "",
    full_response,
    flags=re.DOTALL
).strip()

# --------------------------------------------------
# Display Final Response
# --------------------------------------------------

print("\n" + "=" * 60)
print("HARNESS RESPONSE")
print("=" * 60 + "\n")

if full_response:
    print(full_response)
else:
    print("No assistant text was returned.")

print("\n" + "=" * 60)
print("INVOCATION COMPLETE")
print(f"Session ID: {session_id}")
print("=" * 60)
