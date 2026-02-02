import requests

GATEWAY_URL = "" #REPLACE WITH YOUR GATEWAY ID
TOKEN = "" #REPLACE WITH OAUTH TOKEN 

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
}

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

r = requests.post(GATEWAY_URL, headers=headers, json=payload)
print(r.json())
