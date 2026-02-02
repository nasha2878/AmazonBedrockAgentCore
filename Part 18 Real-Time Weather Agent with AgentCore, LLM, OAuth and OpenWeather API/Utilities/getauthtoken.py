import requests
import base64

TOKEN_URL = "<<domain>>/oauth2/token" # REPLACE WITH YOUR COGNITO DOMAIN NAME
CLIENT_ID = "<< client id>>" # REPLACE WITH YOUr CLIENT ID
CLIENT_SECRET = "<< client secret >>" # REPLACE WITH YOUr CLIENT SECRET

auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/x-www-form-urlencoded"
}

data = {
    "grant_type": "client_credentials",
    "scope": "<< custom scope >>" # REPLACE WITH YOUR CUSTOM SCOPE
}

r = requests.post(TOKEN_URL, headers=headers, data=data)
r.raise_for_status()

token = r.json()["access_token"]
print("Access Token:\n", token)