import requests

GATEWAY_URL = "https://gateway-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp" # REPLACE WITH YOUR GATEWAY URL
TOKEN = "<PASTE TOKEN>" #REPLACE WITH OAUTH TOKEN

payload = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "myWeatherTool___myWeatherTool",
        "arguments": {
            "city": "Chicago"
        }
    }
}

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

r = requests.post(GATEWAY_URL, headers=headers, json=payload)
print(r.json())

