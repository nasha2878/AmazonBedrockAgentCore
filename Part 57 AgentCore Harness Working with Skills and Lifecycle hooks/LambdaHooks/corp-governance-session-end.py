
import json
import boto3
import datetime
import time
import re
import traceback
from urllib.parse import unquote

logs = boto3.client("logs", region_name="us-east-1")

LOG_GROUP = "/corp-governance/audit-trail"
LOG_STREAM = "session-events"

STANDARDS = [
    "corporate-naming-rules",
    "cost-guardrails",
    "sre-telemetry"
]



def diagnostic(message, data=None):
    """Structured diagnostic logging."""

    timestamp = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    record = {
        "diagnostic": True,
        "timestamp": timestamp,
        "message": message
    }

    if data is not None:
        record["data"] = data

    print(json.dumps(record, default=str))


def extract_identity(event):

    headers = event.get("headers", {})

    if not isinstance(headers, dict):
        headers = {}

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

    collected = []

    if isinstance(value, dict):

        for key, item in value.items():

            if key.lower() in [
                "text", "content", "message",
                "input", "output"
            ]:
                collected.extend(collect_text(item))

            elif isinstance(item, (dict, list)):
                collected.extend(collect_text(item))

    elif isinstance(value, list):

        for item in value:
            collected.extend(collect_text(item))

    elif isinstance(value, str):

        collected.append(value)

    return collected



def calculate_duration(event):

    start_time = (
        event.get("sessionStartTime")
        or event.get("session_start_time")
        or event.get("startTime")
    )

    if not start_time:
        return None

    try:

        start = datetime.datetime.fromisoformat(
            start_time.replace("Z", "+00:00")
        )

        if start.tzinfo is None:
            start = start.replace(
                tzinfo=datetime.timezone.utc
            )

        now = datetime.datetime.now(
            datetime.timezone.utc
        )

        return round(
            (now - start).total_seconds(),
            2
        )

    except Exception:
        diagnostic(
            "DURATION CALCULATION FAILED",
            {"start_time": str(start_time)}
        )
        return None


def put_log(entry):

    diagnostic("AUDIT LOG WRITE STARTED", {
        "log_group": LOG_GROUP,
        "log_stream": LOG_STREAM
    })

    try:

        try:
            logs.create_log_stream(
                logGroupName=LOG_GROUP,
                logStreamName=LOG_STREAM
            )

            diagnostic("LOG STREAM CREATED")

        except logs.exceptions.ResourceAlreadyExistsException:
            diagnostic("LOG STREAM ALREADY EXISTS")

        result = logs.put_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=LOG_STREAM,
            logEvents=[{
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(entry)
            }]
        )

        diagnostic("AUDIT LOG WRITE SUCCESSFUL", {
            "next_sequence_token": result.get(
                "nextSequenceToken"
            ),
            "rejected_log_events_info": result.get(
                "rejectedLogEventsInfo"
            )
        })

    except Exception:

        diagnostic(
            "AUDIT LOG WRITE FAILED",
            {"traceback": traceback.format_exc()}
        )

        raise


def lambda_handler(event, context):

    invocation_start = time.time()

    diagnostic("SESSION CLOSE LAMBDA INVOKED", {
        "request_id": context.aws_request_id,
        "function_name": context.function_name,
        "remaining_time_ms": context.get_remaining_time_in_millis()
    })

    try:

        # 1. Validate event structure

        if not isinstance(event, dict):
            raise ValueError("Lifecycle event is not a dictionary")

        diagnostic("EVENT STRUCTURE RECEIVED", {
            "top_level_keys": list(event.keys()),
            "has_headers": isinstance(
                event.get("headers"), dict
            ),
            "has_context": isinstance(
                event.get("context"), dict
            ),
            "has_messages": "messages" in event,
            "has_turns": "turns" in event
        })

        # Log raw event for troubleshooting.
        # Review access controls on the Lambda log group.
        diagnostic("RAW SESSION CLOSE EVENT", event)

        # 2. Extract lifecycle metadata

        session_id = event.get("sessionId", "unknown")
        harness_arn = event.get("harnessArn", "unknown")
        hook_name = event.get("name", "unknown")
        hook_event = event.get("event", "unknown")

        diagnostic("LIFECYCLE METADATA EXTRACTED", {
            "session_id": session_id,
            "harness_arn": harness_arn,
            "hook_name": hook_name,
            "hook_event": hook_event
        })

        # 3. Extract identity

        user_id, user_arn = extract_identity(event)

        invoked_by = (
            user_arn
            if user_arn != "unknown"
            else user_id
        )

        diagnostic("IDENTITY EXTRACTION RESULT", {
            "identity_found": invoked_by != "unknown",
            "user_id_found": user_id != "unknown",
            "user_arn_found": user_arn != "unknown"
        })

        # 5. Calculate duration

        duration = calculate_duration(event)

        diagnostic("DURATION CALCULATION RESULT", {
            "duration_seconds": duration
        })

        # 6. Build audit record

        entry = {
            "event": "INVOCATION_COMPLETED",
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
            "duration_seconds": duration,
            "standards_applied": STANDARDS,
            "lambda_request_id": context.aws_request_id,
            "timestamp": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        }

        diagnostic("AUDIT RECORD PREPARED", {
            "session_id": session_id,
            "field_count": len(entry),
            "event_type": entry["event"]
        })

        # 7. Write audit record

        put_log(entry)

        elapsed = round(
            time.time() - invocation_start,
            3
        )

        diagnostic("SESSION CLOSE LAMBDA COMPLETED", {
            "session_id": session_id,
            "elapsed_seconds": elapsed,
            "decision": "allow"
        })

        return {
            "decision": "allow",
            "reason": "Session close audit record written successfully."
        }

    except Exception as e:

        diagnostic("SESSION CLOSE LAMBDA FAILED", {
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_seconds": round(
                time.time() - invocation_start,
                3
            )
        })

        return {
            "decision": "deny",
            "reason": "Session close audit processing failed."
        }
