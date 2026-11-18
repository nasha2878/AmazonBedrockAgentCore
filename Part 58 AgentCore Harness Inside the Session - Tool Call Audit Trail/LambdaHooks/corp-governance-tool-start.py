import json
import boto3
import datetime

LOG_GROUP  = "/corp-governance/audit-trail"
LOG_STREAM = "tool-call-events"

logs = boto3.client("logs", region_name="us-east-1")

def _put_log(message: str):
    try:
        logs.put_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=LOG_STREAM,
            logEvents=[{
                "timestamp": int(datetime.datetime.utcnow().timestamp() * 1000),
                "message": message
            }]
        )
    except logs.exceptions.ResourceNotFoundException:
        logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
        _put_log(message)

def lambda_handler(event, context):
    print("RAW EVENT:", json.dumps(event))

    hook_context = event.get("context", {})

    entry = {
        "event"        : "TOOL_STARTING",
        "hook_event_id": event.get("hookEventId", "unknown"),
        "tool_name"    : hook_context.get("toolName", "unknown"),   # ← added
        "tool_type"    : hook_context.get("toolType", "unknown"),   # ← added
        "tool_input"   : hook_context.get("toolInput", {}),         # ← added
        "tool_use_id"  : hook_context.get("toolUseId", "unknown"),
        "timestamp"    : datetime.datetime.utcnow().isoformat() + "Z"
    }

    _put_log(json.dumps(entry))
    return { "decision": "allow" }
