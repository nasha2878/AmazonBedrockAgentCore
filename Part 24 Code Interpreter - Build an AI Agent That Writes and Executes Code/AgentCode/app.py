import os
import json
import logging
import boto3
from flask import Flask, request, jsonify
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter

# -------------------------------------------------
# Initialization & Logging
# -------------------------------------------------
flask_app = Flask(__name__)

# Set global logging to INFO so we can see our agent's actions
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Silence the "127.0.0.1 - - [date] GET /ping" spam from Flask/Werkzeug
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# Using Claude 4.5 Global Inference Profile
MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
code_client = CodeInterpreter(AWS_REGION)

# -------------------------------------------------
# Tool Definition
# -------------------------------------------------
CODE_INTERPRETER_TOOL = {
    "toolSpec": {
        "name": "code_interpreter",
        "description": "Execute Python code for math, data analysis, or plotting.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Python code to run"},
                    "language": {"type": "string", "enum": ["python"], "default": "python"}
                },
                "required": ["code", "language"]
            }
        }
    }
}

# -------------------------------------------------
# LLM Caller
# -------------------------------------------------
def call_llm(messages):
    """Calls Bedrock using the Converse API"""
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=messages,
        inferenceConfig={"maxTokens": 2000, "temperature": 0.2},
        toolConfig={"tools": [CODE_INTERPRETER_TOOL]}
    )
    return response["output"]["message"]

# -------------------------------------------------
# Multi-step Tool Routing Loop
# -------------------------------------------------
def run_agent(user_text: str):
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    is_session_active = False

    try:
        while True:
            # 1. Get LLM Response
            assistant_message = call_llm(messages)
            messages.append(assistant_message)

            # 2. Check for Tool Use
            tool_calls = [c for c in assistant_message["content"] if "toolUse" in c]
            
            if not tool_calls:
                # Regular question: No session started, returns instantly
                return next((c["text"] for c in assistant_message["content"] if "text" in c), "I'm not sure.")

            # 3. Lazy Start: Only start the sandbox if Claude wants to use it
            if not is_session_active:
                logger.info(">>> Tool call detected. Starting Code Interpreter session...")
                code_client.start()
                is_session_active = True

            tool_results = []
            for call in tool_calls:
                tool_use = call["toolUse"]
                tool_id = tool_use["toolUseId"]
                tool_args = tool_use["input"]

                if tool_use["name"] == "code_interpreter":
                    logger.info(f">>> Executing Code: {tool_args.get('code')}")
                    
                    # 4. Invoke and Handle the EventStream
                    response = code_client.invoke("executeCode", tool_args)
                    
                    final_result = {"stdout": "", "stderr": ""}
                    
                    # Consuming the stream to get the actual results
                    for event in response.get("stream", []):
                        if "result" in event:
                            res_data = event["result"]
                            if "content" in res_data:
                                for item in res_data["content"]:
                                    if item.get("type") == "text":
                                        final_result["stdout"] += item.get("text", "")
                            if "stderr" in res_data:
                                final_result["stderr"] += res_data.get("stderr", "")

                    # Send back the serializable JSON result
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"text": json.dumps(final_result)}],
                            "status": "success"
                        }
                    })

            # 5. Feed the results back to the LLM
            messages.append({"role": "user", "content": tool_results})
            
    except Exception as e:
        logger.error(f"Error in agent loop: {str(e)}")
        raise e
    finally:
        # Cleanup session only if it was initialized
        if is_session_active:
            logger.info(">>> Stopping Code Interpreter session...")
            code_client.stop()

# -------------------------------------------------
# Flask Routes
# -------------------------------------------------
@flask_app.route("/invocations", methods=["POST"])
def invocations():
    data = request.get_json() or {}
    user_input = data.get("input", {}).get("text", data.get("text", ""))

    try:
        completion = run_agent(user_input)
        return jsonify({"completion": completion, "stop_reason": "end_turn"}), 200
    except Exception as e:
        logger.exception("Agent execution failed")
        return jsonify({"error": str(e)}), 500

@flask_app.route("/ping", methods=["GET"])
def ping():
    # Silently returns 200 OK for AWS health checks
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=8080)
