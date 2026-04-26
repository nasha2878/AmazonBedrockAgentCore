import os
import uuid
import logging
import boto3
from flask import Flask, request, jsonify
from werkzeug.serving import WSGIRequestHandler

# Part 30: ADOT Observability Imports
from opentelemetry import trace, baggage, context

# ADOT automatically initializes the tracer via the Docker wrapper
tracer = trace.get_tracer(__name__)

# 1. Silence Flask/Health-check spam
WSGIRequestHandler.log = lambda self, type, message, *args: None
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# 2. Flask app setup
flask_app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 3. AWS Clients
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")

agentcore = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# 4. Managed Browser Identifier
BROWSER_ID = "aws.browser.v1"

# 5. System Prompt
SYSTEM_PROMPT = """
You are a market intelligence analyst for REI. Use the browser tool to research competitors.
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
    session_uuid = str(uuid.uuid4())
    
    # --- GOAL 1: TRACE THE JOURNEY (Parent Span) ---
    with tracer.start_as_current_span("REI_Market_Intelligence_Request") as span:
        
        # --- GOAL 3: ACCOUNTABILITY (Baggage & Attributes) ---
        ctx = baggage.set_baggage("session.id", session_uuid)
        token = context.attach(ctx)
        span.set_attribute("rei.session_id", session_uuid)
        span.set_attribute("rei.user_input", user_text)

        messages = [{"role": "user", "content": [{"text": user_text}]}]
        session_id = None

        try:
            while True:
                # --- GOAL 2: ISOLATE LATENCY (Model Span) ---
                with tracer.start_as_current_span("LLM_Reasoning_Phase") as model_span:
                    response = bedrock_runtime.converse(
                        modelId=MODEL_ID,
                        messages=messages,
                        system=[{"text": SYSTEM_PROMPT}],
                        toolConfig={"tools": [BROWSER_TOOL_SPEC]}
                    )
                    model_span.set_attribute("gen_ai.model_id", MODEL_ID)
                
                assistant_msg = response["output"]["message"]
                messages.append(assistant_msg)

                tool_requests = [c["toolUse"] for c in assistant_msg["content"] if "toolUse" in c]
                if not tool_requests:
                    final_res = next((c["text"] for c in assistant_msg["content"] if "text" in c), "Research complete.")
                    span.set_attribute("rei.final_insight", final_res)
                    return final_res

                if not session_id:
                    with tracer.start_as_current_span("Start_Browser_Session"):
                        logger.info(">>> Starting Managed Browser Session")
                        session_resp = agentcore.start_browser_session(browserIdentifier=BROWSER_ID)
                        session_id = session_resp["sessionId"]
                        span.set_attribute("rei.browser_session_id", session_id)

                tool_results = []
                for req in tool_requests:
                    query = req["input"].get("query", "")
                    logger.info(f"Executing web search for: {query}")

                    # --- GOAL 2: ISOLATE LATENCY (Browser Span) ---
                    with tracer.start_as_current_span("Browser_Tool_Live_Research") as tool_span:
                        tool_span.set_attribute("rei.competitor_query", query)
                        
                        bt_res = agentcore.update_browser_stream(
                            browserIdentifier=BROWSER_ID,
                            sessionId=session_id,
                            streamUpdate={"automationStreamUpdate": {"streamStatus": "ENABLED"}}
                        )

                        res_text = f"Researching: {query}..."
                        for event in bt_res.get("stream", []):
                            if "result" in event:
                                for item in event["result"].get("content", []):
                                    if "text" in item:
                                        res_text = item["text"]
                        
                        # --- GOAL 3: ACCOUNTABILITY (Evidence) ---
                        tool_span.set_attribute("rei.raw_browser_output", res_text[:500])

                        tool_results.append({
                            "toolResult": {
                                "toolUseId": req["toolUseId"],
                                "content": [{"text": res_text}],
                                "status": "success"
                            }
                        })

                messages.append({"role": "user", "content": tool_results})

        except Exception as e:
            span.record_exception(e)
            logger.error(f"Agent Loop Error: {e}")
            return f"System Error: {str(e)}"
        finally:
            if session_id:
                try:
                    agentcore.stop_browser_session(browserIdentifier=BROWSER_ID, sessionId=session_id)
                except Exception: pass
            context.detach(token)

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
