import os
import json
import logging
import boto3
import urllib.request
from flask import Flask, request, jsonify
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from botocore.config import Config
from werkzeug.serving import WSGIRequestHandler

# 1. Silence Flask/Health-check spam
WSGIRequestHandler.log = lambda self, type, message, *args: None
logging.getLogger('werkzeug').setLevel(logging.ERROR)

flask_app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")

# Custom Tool ID with "Public network" mode enabled for S3 access
CUSTOM_TOOL_ID = os.environ.get("CUSTOM_TOOL_ID", "<<YOUR CODE INTERPRETER ID>>")

s3_client = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
code_client = CodeInterpreter(AWS_REGION)

# 2. Simplified System Prompt 
SYSTEM_PROMPT = """
You are a data analyst. When a user provides an S3 URI:
1. Extract the URI and pass it to the 's3_uri' parameter.
2. In your code, assume the file is in the local directory (filename only).
3. Perform text-based analysis (summary, stats, trends) and print the results.
"""

CODE_INTERPRETER_TOOL = {
    "toolSpec": {
        "name": "code_interpreter",
        "description": "Execute Python for data analysis. Use 's3_uri' for S3 files.",
        "inputSchema": {
            "json": {
                "type": "object", 
                "properties": {
                    "code": {"type": "string"}, 
                    "s3_uri": {"type": "string"}
                }, 
                "required": ["code"]
            }
        }
    }
}

# 3. Core Agent Loop
def run_agent(user_text: str):
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    is_session_active = False

    try:
        while True:
            response = bedrock.converse(
                modelId=MODEL_ID, system=[{"text": SYSTEM_PROMPT}], 
                messages=messages, toolConfig={"tools": [CODE_INTERPRETER_TOOL]}
            )
            assistant_msg = response["output"]["message"]
            messages.append(assistant_msg)

            tool_calls = [c for c in assistant_msg["content"] if "toolUse" in c]
            if not tool_calls:
                return next((c["text"] for c in assistant_msg["content"] if "text" in c), "Analysis done.")

            if not is_session_active:
                logger.info(f">>> Starting session: {CUSTOM_TOOL_ID}")
                code_client.start(identifier=CUSTOM_TOOL_ID)
                is_session_active = True

            tool_results = []
            for call in tool_calls:
                args = call["toolUse"]["input"]
                s3_uri = args.get("s3_uri")
                
                if s3_uri:
                    # Clean S3 parsing for pre-signed GET
                    uri_raw = s3_uri.replace("s3://", "")
                    bucket = uri_raw.split("/", 1)[0]
                    key = uri_raw.split("/", 1)[1]
                    filename = key.split("/")[-1]
                    
                    get_url = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key})
                    
                    full_code = f"""
import urllib.request, pandas as pd
urllib.request.urlretrieve('{get_url}', '{filename}')
{args['code']}
"""
                else:
                    full_code = args['code']

                # Invoke and capture stream
                sandbox_res = code_client.invoke("executeCode", {"code": full_code, "language": "python"})
                
                res_text = ""
                for event in sandbox_res.get("stream", []):
                    if "result" in event:
                        res_text += "".join([i.get("text", "") for i in event["result"].get("content", []) if i.get("type") == "text"])

                # Handle empty output to prevent Bedrock ValidationErrors
                tool_results.append({
                    "toolResult": {
                        "toolUseId": call["toolUse"]["toolUseId"], 
                        "content": [{"text": res_text if res_text.strip() else "Task completed."}], 
                        "status": "success"
                    }
                })

            messages.append({"role": "user", "content": tool_results})
            
    finally:
        if is_session_active:
            code_client.stop()

# 4. Standard Flask Routes
@flask_app.route("/invocations", methods=["POST"])
def invocations():
    data = request.get_json() or {}
    user_input = data.get("input", {}).get("text", data.get("text", ""))
    return jsonify({"completion": run_agent(user_input)}), 200

@flask_app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=8080)
