
import json
import boto3
import datetime
import time
import re
from urllib.parse import unquote

REGION = "us-east-1"

logs = boto3.client("logs", region_name=REGION)

LOG_GROUP = "/corp-governance/audit-trail"
LOG_STREAM = "session-events"

RESOURCE_KEYWORDS = [
    "SQS",
    "SNS",
    "S3",
    "LAMBDA",
    "EC2",
    "RDS",
    "DYNAMODB"
]


def extract_identity(event):

    headers = event.get("headers", {})

    if not isinstance(headers, dict):
        return "unknown", "unknown"

    normalized_headers = {
        str(k).lower(): v
        for k, v in headers.items()
    }

    baggage = normalized_headers.get("baggage", "")

    user_id = "unknown"
    user_arn = "unknown"

    for item in baggage.split(","):

        key, separator, value = item.strip().partition("=")

        if not separator:
            continue

        value = unquote(value.strip())

        if key.strip() == "user.id":
            user_id = value

        elif key.strip() == "user.arn":
            user_arn = value

    return user_id, user_arn


def collect_text(value):
    """
    Extract text from nested Harness message structures.
    """

    collected = []

    if isinstance(value, dict):

        for key, item in value.items():

            if key.lower() == "text" and isinstance(item, str):
                collected.append(item)

            elif isinstance(item, (dict, list)):
                collected.extend(collect_text(item))

    elif isinstance(value, list):

        for item in value:
            collected.extend(collect_text(item))

    return collected


def extract_resources(event):
    """
    Extract AWS services mentioned in incoming user messages.
    """

    context = event.get("context", {})

    sources = [
        context.get("messages", []) if isinstance(context, dict) else [],
        event.get("messages", []),
        event.get("turns", [])
    ]

    all_text = " ".join(
        text
        for source in sources
        for text in collect_text(source)
    )

    found = []

    for keyword in RESOURCE_KEYWORDS:

        pattern = r"\b" + re.escape(keyword) + r"\b"

        if re.search(pattern, all_text, re.IGNORECASE):
            found.append(keyword)

    print("RESOURCE EXTRACTION:", json.dumps({
        "text_length": len(all_text),
        "resources_requested": found
    }))

    return found


def put_audit_log(entry):

    try:
        logs.create_log_stream(
            logGroupName=LOG_GROUP,
            logStreamName=LOG_STREAM
        )

    except logs.exceptions.ResourceAlreadyExistsException:
        pass

    logs.put_log_events(
        logGroupName=LOG_GROUP,
        logStreamName=LOG_STREAM,
        logEvents=[{
            "timestamp": int(time.time() * 1000),
            "message": json.dumps(entry)
        }]
    )


def lambda_handler(event, context):

    print(
        "RAW BEFORE INVOCATION EVENT:",
        json.dumps(event, default=str)
    )

    session_id = event.get("sessionId", "unknown")
    harness_arn = event.get("harnessArn", "unknown")
    hook_name = event.get("name", "unknown")
    hook_event = event.get("event", "unknown")

    # 1. Extract identity

    user_id, user_arn = extract_identity(event)

    invoked_by = (
        user_arn
        if user_arn != "unknown"
        else user_id
    )

    # 2. Extract AWS services from incoming messages

    resources = extract_resources(event)

    # 3. Construct SESSION_OPENED audit record

    entry = {
        "event": "INVOCATION_STARTED",
        "session_id": session_id,
        "invoked_by": invoked_by,
        "authenticated_principal": user_arn,
        "user_id": user_id,
        "invoked_by_type": (
            "propagated_identity"
            if invoked_by != "unknown"
            else "unknown"
        ),
        "harness_arn": harness_arn,
        "hook_name": hook_name,
        "hook_event": hook_event,
        "harness": "corp-governance-agent",
        "resources_requested": resources,
        "lambda_request_id": context.aws_request_id,
        "timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    }

    # 4. Write audit record

    try:

        put_audit_log(entry)

    except Exception as e:

        print("AUDIT LOGGING ERROR:", str(e))

        return {
            "decision": "deny",
            "reason": "Unable to write governance audit record."
        }

    # 5. Require identity

    if invoked_by == "unknown":

        return {
            "decision": "deny",
            "reason": "Authenticated principal not found."
        }

    print("SESSION OPEN PROCESSING COMPLETE:", session_id)

    return {
        "decision": "allow",
        "reason": "Session identity verified and audit context logged."
    }
