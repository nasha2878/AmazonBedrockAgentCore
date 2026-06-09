import os
import json
import logging
import base64
import requests
import boto3
import uuid
from flask import Flask, request, jsonify
from typing import TypedDict, List, Dict, Any, Annotated
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore import BedrockAgentCoreApp

# --------------------------------------------------
# LangGraph imports
# --------------------------------------------------
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# --------------------------------------------------
# CRITICAL: Enable LangChain instrumentation
# --------------------------------------------------
LangchainInstrumentor().instrument()

# --------------------------------------------------
# Clean logging setup
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable noisy loggers
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("opentelemetry").setLevel(logging.WARNING)

# --------------------------------------------------
# AgentCore and Flask setup
# --------------------------------------------------
agent = BedrockAgentCoreApp()
flask_app = Flask(__name__)

# --------------------------------------------------
# AWS Config
# --------------------------------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
GATEWAY_URL = os.environ.get("GATEWAY_URL")
AGENT_SECRET = os.environ.get("AGENT_SECRET")
MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
secrets = boto3.client("secretsmanager", region_name=AWS_REGION)

# --------------------------------------------------
# State Definition
# --------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    tools_available: List[Dict[str, Any]]
    oauth_token: str
    tool_outputs: List[Dict[str, Any]]
    slack_calls: List[tuple]
    final_answer: str
    planned_actions: List[Dict[str, Any]]
    session_id: str

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
def extract_json(text: str):
    if not text:
        return None
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    s = text.find('[')
    e = text.rfind(']')
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass

    s = text.find('{')
    e = text.rfind('}')
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass

    return None

def get_oauth_token():
    secret_value = secrets.get_secret_value(SecretId=AGENT_SECRET)
    secret = json.loads(secret_value["SecretString"])

    auth = base64.b64encode(
        f"{secret['CLIENT_ID']}:{secret['CLIENT_SECRET']}".encode()
    ).decode()

    headers = {
        "Authorization": "Basic " + auth,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials",
        "scope": secret["SCOPE"]
    }

    response = requests.post(secret["TOKEN_URL"], headers=headers, data=data, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]

def list_tools(token: str):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    response = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json().get("result", {}).get("tools", [])

def call_tool(token: str, name: str, arguments: dict):
    logger.info(f"TOOL: {name}")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }

    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    response = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    return response.json()

def call_llm(messages):
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.2
    }

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body).encode("utf-8"),
        contentType="application/json",
        accept="application/json"
    )

    data = json.loads(response["body"].read())
    content = data.get("content", "")
    if isinstance(content, list) and content:
        return content[0].get("text", "")
    return content

def is_slack_post_tool(tool_name: str, tool_def: dict) -> bool:
    name = (tool_name or "").lower()
    desc = (tool_def.get("description") or "").lower()
    return (
        ("slack" in name and ("post" in name or "message" in name))
        or ("slack" in desc and "message" in desc)
    )

# --------------------------------------------------
# LangGraph Node Functions
# --------------------------------------------------
def initialize_state(state: AgentState) -> AgentState:
    logger.info(f"Session {state['session_id'][:8]}: Init")
    
    token = get_oauth_token()
    tools = list_tools(token)
    
    return {
        **state,
        "oauth_token": token,
        "tools_available": tools,
        "tool_outputs": [],
        "slack_calls": [],
        "planned_actions": [],
        "messages": [HumanMessage(content=state["user_input"])]
    }

def plan_actions(state: AgentState) -> AgentState:
    logger.info(f"Session {state['session_id'][:8]}: Planning")
    
    tools = state["tools_available"]
    user_text = state["user_input"]
    
    decision_prompt = f"""
You are an AI agent with multiple tools.

TOOLS AVAILABLE:
{json.dumps(tools, indent=2)}

RULES:
- Return ONLY a JSON list.
- Each item must be either:

1. Tool call:
   {{
     "action": "tool",
     "name": "<exact tool name>",
     "arguments": {{...}}
   }}

2. Final answer:
   {{
     "action": "answer"
   }}

If the user explicitly provides Slack message content,
call the Slack tool directly using that content.

No extra text.

USER INPUT:
{user_text}
"""

    raw = call_llm([{"role": "user", "content": decision_prompt}])
    actions = extract_json(raw)
    
    if not actions:
        return {
            **state,
            "final_answer": call_llm([{"role": "user", "content": user_text}]),
            "planned_actions": []
        }
    
    if not isinstance(actions, list):
        actions = [actions]
    
    return {
        **state,
        "planned_actions": actions
    }

def execute_data_tools(state: AgentState) -> AgentState:
    logger.info(f"Session {state['session_id'][:8]}: Executing tools")
    
    actions = state.get("planned_actions", [])
    tools_by_name = {t.get("name"): t for t in state["tools_available"] if t.get("name")}
    
    tool_outputs = state["tool_outputs"].copy()
    slack_calls = state["slack_calls"].copy()
    messages = state["messages"].copy()
    
    for action in actions:
        if action.get("action") == "tool":
            name = action.get("name")
            args = action.get("arguments", {}) or {}
            tool_def = tools_by_name.get(name, {})
            
            if is_slack_post_tool(name, tool_def):
                slack_calls.append((name, args))
                continue
            
            result = call_tool(state["oauth_token"], name, args)
            tool_outputs.append({"name": name, "result": result})
            messages.append(AIMessage(content=f"Used tool {name}"))
    
    return {
        **state,
        "tool_outputs": tool_outputs,
        "slack_calls": slack_calls,
        "messages": messages
    }

def handle_slack_tools(state: AgentState) -> AgentState:
    logger.info(f"Session {state['session_id'][:8]}: Slack handling")
    
    slack_calls = state["slack_calls"]
    tool_outputs = state["tool_outputs"].copy()
    user_text = state["user_input"]
    
    if not slack_calls:
        return state
    
    if not tool_outputs:
        for name, args in slack_calls:
            if not args.get("text"):
                args["text"] = user_text
            
            result = call_tool(state["oauth_token"], name, args)
            tool_outputs.append({"name": name, "result": result})
    
    else:
        slack_prompt = f"""
Generate the final message to be delivered externally.

STRICT RULES:
- Use ONLY factual data from tool results.
- Do NOT invent anything.
- Do NOT include placeholders.
- Do NOT include raw JSON.
- Return plain text only.

User request:
{user_text}

Tool results:
{json.dumps(tool_outputs, indent=2)}
"""
        
        final_slack_message = call_llm([{"role": "user", "content": slack_prompt}]).strip()
        
        for name, args in slack_calls:
            args["text"] = final_slack_message
            result = call_tool(state["oauth_token"], name, args)
            tool_outputs.append({"name": name, "result": result})
    
    return {
        **state,
        "tool_outputs": tool_outputs
    }

def generate_final_response(state: AgentState) -> AgentState:
    logger.info(f"Session {state['session_id'][:8]}: Generating response")
    
    user_text = state["user_input"]
    tool_outputs = state["tool_outputs"]
    
    if state.get("final_answer"):
        return state
    
    summary_prompt = f"""
Answer the user's original request clearly.

- Do NOT mention tool names.
- Do NOT include raw JSON.
- If Slack posting occurred successfully, state that it has been sent.
- If Slack failed, clearly state the reason.
- Use past tense.

User question:
{user_text}

Tool results:
{json.dumps(tool_outputs, indent=2)}
"""
    
    final_answer = call_llm([{"role": "user", "content": summary_prompt}])
    messages = state["messages"].copy()
    messages.append(AIMessage(content=final_answer))
    
    return {
        **state,
        "final_answer": final_answer,
        "messages": messages
    }

def should_continue(state: AgentState) -> str:
    if state.get("final_answer"):
        return END
    
    actions = state.get("planned_actions", [])
    if not actions:
        return END
    
    has_tools = any(action.get("action") == "tool" for action in actions)
    if has_tools:
        return "execute_data_tools"
    
    return END

# --------------------------------------------------
# Build LangGraph Workflow
# --------------------------------------------------
def create_agent_workflow():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("initialize", initialize_state)
    workflow.add_node("plan", plan_actions)
    workflow.add_node("execute_data_tools", execute_data_tools)
    workflow.add_node("handle_slack", handle_slack_tools)
    workflow.add_node("generate_response", generate_final_response)
    
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "plan")
    workflow.add_conditional_edges(
        "plan",
        should_continue,
        {
            "execute_data_tools": "execute_data_tools",
            END: "generate_response"
        }
    )
    workflow.add_edge("execute_data_tools", "handle_slack")
    workflow.add_edge("handle_slack", "generate_response")
    workflow.add_edge("generate_response", END)
    
    return workflow.compile()

agent_workflow = create_agent_workflow()

# --------------------------------------------------
# Simple Session Handling
# --------------------------------------------------
def run_agent(user_text: str) -> str:
    session_id = str(uuid.uuid4())
    logger.info(f"Session {session_id[:8]}: Starting")
    
    initial_state: AgentState = {
        "messages": [],
        "user_input": user_text,
        "tools_available": [],
        "oauth_token": "",
        "tool_outputs": [],
        "slack_calls": [],
        "final_answer": "",
        "planned_actions": [],
        "session_id": session_id
    }
    
    final_state = agent_workflow.invoke(initial_state)
    
    logger.info(f"Session {session_id[:8]}: Complete")
    return final_state["final_answer"]

# --------------------------------------------------
# Flask Endpoints
# --------------------------------------------------
@flask_app.route("/", methods=["POST"])
def root():
    return invocations()

@flask_app.route("/invocations", methods=["POST"])
def invocations():
    payload = request.get_json() or {}
    user_text = payload.get("input", {}).get("text", "")
    
    result = run_agent(user_text)
    return jsonify({"completion": result, "stop_reason": "end_turn"}), 200

@flask_app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=8080)
