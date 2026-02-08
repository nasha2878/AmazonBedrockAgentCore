import requests
import base64
import json

# =========================
# REPLACE CONFIG AND TOOL NAMES
# =========================

REGION = "us-east-1"    #REPLACE 
GATEWAY_URL = "https://<YOUR-GATEWAY-ID>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp" #REPLACE
TOKEN_URL = "https://<YOUR-COGNITO-DOMAIN>/oauth2/token" #REPLACE
CLIENT_ID = "<CLIENT_ID>" #REPLACE
CLIENT_SECRET = "<CLIENT_SECRET>" #REPLACE
SCOPE = "<CUSTOM_SCOPE>" #REPLACE

# Explicit tool names (REPLACE WITH WHAT YOU SEE IN THE TOOL LISTING)
WEATHER_TOOL = "myWeatherTool___getCityWeather"
LOCATION_TOOL = "getLocationCoordinates___forwardGeocode"
SLACK_TOOL = "Slacknotifier___chatPostMessage"


# =========================
# AUTH
# =========================

def get_access_token():
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials",
        "scope": SCOPE
    }

    r = requests.post(TOKEN_URL, headers=headers, data=data)
    r.raise_for_status()
    return r.json()["access_token"]


# =========================
# GATEWAY CALLS
# =========================

def list_tools(token):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.post(GATEWAY_URL, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["result"]["tools"]


def call_tool(token, tool_name, arguments):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.post(GATEWAY_URL, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()


# =========================
# DISPLAY HELPERS
# =========================

def print_tools(tools):
    print("\n=== Available Gateway Tools ===")
    for i, t in enumerate(tools, start=1):
        print(f"{i}. {t['name']}")


# =========================
# MAIN
# =========================

def main():
    print("\n=== Multi-Tool Gateway Interactive Test ===")

    token = get_access_token()

    while True:
        print("""
1. List all available tools
2. Get weather for a city
3. Get location coordinates
4. Send Slack message
0. Exit
""")

        choice = input("Select an option: ").strip()

        if choice == "1":
            tools = list_tools(token)
            print_tools(tools)

        elif choice == "2":
            city = input("Enter city name: ")
            resp = call_tool(token, WEATHER_TOOL, {"city": city})
            print("\n=== Tool Response ===")
            print(json.dumps(resp, indent=2))

        elif choice == "3":
            location = input("Enter location (e.g. Boston): ")
            resp = call_tool(
                token,
                LOCATION_TOOL,
                {
                    "q": location,
                    "format": "json",
                    "key": "dummy"  # required so gateway can inject API key
                }
            )
            print("\n=== Tool Response ===")
            print(json.dumps(resp, indent=2))

        elif choice == "4":
            channel = input("Enter Slack channel (e.g. #social): ")
            message = input("Enter message: ")
            resp = call_tool(
                token,
                SLACK_TOOL,
                {
                    "channel": channel,
                    "text": message
                }
            )
            print("\n=== Tool Response ===")
            print(json.dumps(resp, indent=2))

        elif choice == "0":
            print("Exiting.")
            break

        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
