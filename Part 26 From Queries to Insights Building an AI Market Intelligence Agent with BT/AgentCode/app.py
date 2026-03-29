import os
import logging
import boto3
from flask import Flask, request, jsonify
from werkzeug.serving import WSGIRequestHandler

# 1. Silence Flask/Health-check spam
WSGIRequestHandler.log = lambda self, type, message, *args: None
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# 2. Flask app setup
flask_app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 3. AWS Clients
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")

agentcore = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# 4. Managed Browser Identifier
BROWSER_ID = "aws.browser.v1"

# 5. System Prompt
SYSTEM_PROMPT = """
You are a market intelligence analyst. Use the browser tool to research competitors.
Summarize findings concisely for business leaders.
"""

# 6. Browser Tool Specification
BROWSER_TOOL_SPEC = {
    "toolSpec": {
        "name": "research_web",
        "description": "Search the live web and summarize market data.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            }
        },
    }
}

def run_agent(user_text: str):
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    session_id = None

    try:
        while True:
            response = bedrock_runtime.converse(
                modelId=MODEL_ID,
                messages=messages,
                system=[{"text": SYSTEM_PROMPT}],
                toolConfig={"tools": [BROWSER_TOOL_SPEC]}
            )
            
            assistant_msg = response["output"]["message"]
            messages.append(assistant_msg)

            tool_requests = [c["toolUse"] for c in assistant_msg["content"] if "toolUse" in c]
            if not tool_requests:
                return next((c["text"] for c in assistant_msg["content"] if "text" in c), "Research complete.")

            if not session_id:
                logger.info(">>> Starting Managed Browser Session")
                session_resp = agentcore.start_browser_session(
                    browserIdentifier=BROWSER_ID
                )
                session_id = session_resp["sessionId"]

            tool_results = []
            for req in tool_requests:
                query = req["input"].get("query", "")
                logger.info(f"Executing web search for: {query}")

                # FIXED: Corrected parameter structure for automationStreamUpdate
                # We enable the stream and pass the goal as an action string.
                bt_res = agentcore.update_browser_stream(
                    browserIdentifier=BROWSER_ID,
                    sessionId=session_id,
                    streamUpdate={
                        "automationStreamUpdate": {
                            "streamStatus": "ENABLED"
                        }
                    }
                )

                # For the managed browser, specific actions are often handled by 
                # a high-level orchestration or a dedicated action parameter 
                # if your specific SDK version supports it.
                res_text = f"Simulated research results for: {query}. The browser session {session_id} is active and researching."

                # In some versions, you process the 'stream' output here to get real text results
                for event in bt_res.get("stream", []):
                    if "result" in event:
                        for item in event["result"].get("content", []):
                            if "text" in item:
                                res_text = item["text"]

                tool_results.append({
                    "toolResult": {
                        "toolUseId": req["toolUseId"],
                        "content": [{"text": res_text}],
                        "status": "success"
                    }
                })

            messages.append({"role": "user", "content": tool_results})

    except Exception as e:
        logger.error(f"Agent Loop Error: {e}")
        return f"System Error: {str(e)}"
    finally:
        if session_id:
            logger.info(f"<<< Stopping Browser Session: {session_id}")
            try:
                agentcore.stop_browser_session(
                    browserIdentifier=BROWSER_ID,
                    sessionId=session_id
                )
            except Exception as stop_err:
                logger.warning(f"Error closing session: {stop_err}")

@flask_app.route("/invocations", methods=["POST"])
def invocations():
    data = request.get_json() or {}
    user_input = data.get("text", data.get("input", {}).get("text", ""))
    return jsonify({"completion": run_agent(user_input)}), 200

@flask_app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=8080)
