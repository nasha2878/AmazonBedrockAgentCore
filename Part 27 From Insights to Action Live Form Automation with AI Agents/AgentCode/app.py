import os
import asyncio
import logging
import re
import json
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright
import boto3

# ----------------------
# Logging
# ----------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)

# ----------------------
# Flask app
# ----------------------
app = Flask(__name__, static_folder="static")

# ----------------------
# AWS Bedrock / LLM
# ----------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

SYSTEM_PROMPT = """
You are a helpful assistant. Decide if a tool call is needed.
If the user provides a form URL with {{…}} fields, return JSON like:
{
  "tool": {
    "name": "submit_form",
    "url": "...",
    "fields": {...}
}
}
After the tool executes, curate a friendly business-ready message for the user.
Return ONLY the curated message — do NOT include any JSON or tool instructions.
"""

# ----------------------
# Playwright tool
# ----------------------
async def run_playwright(url, fields):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        logger.info("Navigating to URL: %s", url)
        await page.goto(url, timeout=30000)

        for name, value in fields.items():
            logger.info("Filling field '%s' with value '%s'", name, value)
            await page.fill(f"input[name='{name}']", value)

        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle")
        html = await page.content()
        await browser.close()
        return html

# ----------------------
# Extract fields from {{…}}
# ----------------------
def parse_fields_from_prompt(prompt_text):
    block_match = re.search(r"\{\{(.*?)\}\}", prompt_text, re.DOTALL)
    fields = {}
    if block_match:
        fields_text = block_match.group(1)
        for line in fields_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                fields[key] = value.strip()
    return fields

# ----------------------
# Call LLM
# ----------------------
def call_llm(user_text, tool_result=None, system_prompt=SYSTEM_PROMPT):
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    if tool_result:
        messages.append({"role": "user", "content": [{"text": tool_result}]})
    try:
        resp = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=messages,
            system=[{"text": system_prompt}],
        )
        return resp
    except Exception as e:
        logger.exception("LLM call failed")
        return {"error": str(e)}

# ----------------------
# Agent logic
# ----------------------
def run_agent(user_text):
    fields = parse_fields_from_prompt(user_text)

    # Step 1: Ask LLM if tool call is needed
    llm_response = call_llm(user_text)

    # Step 2: Extract text content from LLM
    content = llm_response.get("output", {}).get("message", {}).get("content", [])
    llm_text = " ".join([c.get("text", "") for c in content])

    # Check for JSON tool block in LLM output
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", llm_text, re.DOTALL)
    if json_match:
        try:
            tool_json = json.loads(json_match.group(1))
            if "tool" in tool_json and tool_json["tool"].get("name") == "submit_form":
                tool = tool_json["tool"]
                url = tool["url"]
                tool_fields = fields if fields else tool.get("fields", {})

                # Step 3: Execute Playwright
                html_result = asyncio.run(run_playwright(url, tool_fields))

                # Step 4: Send Playwright result back to LLM for curation
                system_curate_prompt = (
                    "You are a helpful assistant. "
                    "The user submitted a form. "
                    "Curate a friendly business-ready message for the user. "
                    "Do NOT include any JSON or tool instructions."
                )
                curated_response = call_llm(user_text, tool_result=html_result, system_prompt=system_curate_prompt)

                # Extract only text content
                curated_content = curated_response.get("output", {}).get("message", {}).get("content", [])
                return " ".join([c.get("text", "") for c in curated_content])
        except Exception as e:
            logger.warning(f"Error parsing LLM tool JSON: {e}")

    # Step 5: No tool call, return LLM text
    return llm_text

# ----------------------
# Flask endpoints
# ----------------------
@app.route("/invocations", methods=["POST"])
def invocations():
    data = request.get_json() or {}
    user_input = data.get("text", data.get("input", {}).get("text", ""))
    logger.info("Received user input: %s", user_input)
    response_text = run_agent(user_input)
    return jsonify({"response": response_text}), 200

@app.route("/submit_form", methods=["POST"])
def submit_form():
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    return f"<h2>✅ Form submitted successfully!</h2><ul><li>first_name: {first_name}</li><li>last_name: {last_name}</li><li>email: {email}</li></ul>"

@app.route("/<path:filename>", methods=["GET"])
def serve_static_file(filename):
    return app.send_static_file(filename)

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)