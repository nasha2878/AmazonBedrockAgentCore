# app.py
from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

# Configuration - hardcoded region, environment variables for gateway and token
GATEWAY_URL = os.environ.get('GATEWAY_URL', 'YOUR_GATEWAY_URL_HERE')
OAUTH_TOKEN = os.environ.get('OAUTH_TOKEN', 'YOUR_OAUTH_TOKEN_HERE')
AWS_REGION = 'us-east-1'  # Hardcoded as requested

# Tool name from your gateway configuration
WEATHER_TOOL_NAME = "myWeatherTool___myWeatherTool" #REPLACE WITH YOUR TOOL NAME

def call_gateway_tool(tool_name, parameters):
    """Call AgentCore Gateway to invoke Lambda tools with OAuth token"""
    
    try:
        print(f"ðŸ”§ Calling gateway tool: {tool_name}")
        print(f"ðŸ“‹ Parameters: {json.dumps(parameters, indent=2)}")
        
        # Prepare the MCP request payload matching your schema
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters
            }
        }
        
        # Headers with OAuth token from environment
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {OAUTH_TOKEN}'
        }
        
        print(f"ðŸŒ Making request to gateway: {GATEWAY_URL}")
        print(f"ðŸ” Using OAuth token: {OAUTH_TOKEN[:20]}..." if OAUTH_TOKEN else "âŒ No OAuth token")
        print(f"ðŸ“¤ Request payload: {json.dumps(payload, indent=2)}")
        
        # Make the request to gateway
        response = requests.post(
            GATEWAY_URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=30
        )
        
        print(f"ðŸ“¡ Gateway response status: {response.status_code}")
        
        if response.status_code == 200:
            # Add JSON error handling for gateway response
            try:
                result = response.json()
                print(f"âœ… Gateway response: {json.dumps(result, indent=2)}")
                return result
            except json.JSONDecodeError:
                # If it's not JSON, return the raw text
                raw_text = response.text
                print(f"âš ï¸ Non-JSON response: {raw_text}")
                return {"result": {"content": raw_text}}
        else:
            error_text = response.text
            print(f"âŒ Gateway error response: {error_text}")
            return {"error": f"Gateway call failed: {response.status_code} - {error_text}"}
            
    except Exception as e:
        print(f"âŒ Exception calling gateway: {str(e)}")
        return {"error": f"Exception calling gateway: {str(e)}"}

def get_weather(city):
    """Get weather for a city by calling the gateway with correct tool name"""
    
    print(f"ðŸŒ¤ï¸ Getting weather for '{city}' via gateway...")
    
    # Prepare parameters matching your schema: {"city": "string"}
    parameters = {"city": city}
    
    # Call your Lambda function through the gateway using the correct tool name
    result = call_gateway_tool(WEATHER_TOOL_NAME, parameters)
    
    if "error" in result:
        return f"Error getting weather: {result['error']}"
    
    # Extract the result from MCP response
    if "result" in result:
        # Check different possible response formats
        if "content" in result["result"]:
            weather_data = result["result"]["content"]
            return f"Weather in {city}: {weather_data}"
        elif "text" in result["result"]:
            weather_data = result["result"]["text"]
            return f"Weather in {city}: {weather_data}"
        elif isinstance(result["result"], str):
            return f"Weather in {city}: {result['result']}"
        else:
            # Return whatever we got back from Lambda
            return f"Weather data for {city}: {json.dumps(result['result'])}"
    else:
        return f"Unexpected response format for {city}: {json.dumps(result)}"

@app.route('/invocations', methods=['POST'])
def invocations():
    """Handle agent invocations"""
    
    try:
        # Add debugging to see what we're actually receiving
        print(f"ðŸ“¥ Raw request data: {request.data}")
        print(f"ðŸ“¥ Request content type: {request.content_type}")
        print(f"ðŸ“¥ Request headers: {dict(request.headers)}")
        
        # FIX: Handle any content type - force JSON parsing
        try:
            if request.data:
                # Parse JSON regardless of content-type
                data = json.loads(request.data.decode('utf-8'))
            else:
                data = None
        except Exception as json_error:
            print(f"âŒ JSON parsing error: {json_error}")
            return jsonify({
                "completion": f"Error parsing request JSON: {json_error}. Raw data: {request.data.decode('utf-8', errors='ignore')}",
                "stop_reason": "end_turn"
            }), 200
        
        if data is None:
            print("âŒ No data received")
            return jsonify({
                "completion": "Error: No data received in request",
                "stop_reason": "end_turn"
            }), 200
            
        print(f"ðŸ“¥ Parsed request: {json.dumps(data, indent=2)}")
        
        # Extract the user message
        if 'input' in data and 'text' in data['input']:
            user_message = data['input']['text']
            print(f"ðŸ‘¤ User message: {user_message}")
            
            # Simple intent detection for weather queries
            if any(word in user_message.lower() for word in ['weather', 'temperature', 'forecast', 'climate']):
                # Extract city from message
                city = extract_city_from_message(user_message)
                print(f"ðŸ™ï¸ Detected city: {city}")
                
                # Call gateway to get weather using correct tool name
                weather_response = get_weather(city)
                
                response = {
                    "completion": weather_response,
                    "stop_reason": "end_turn"
                }
                
            else:
                # Non-weather queries
                response = {
                    "completion": "I'm a weather agent powered by myWeatherTool. I can help you get weather information for any city. Just ask 'What's the weather in [city name]?'",
                    "stop_reason": "end_turn"
                }
            
        else:
            response = {
                "completion": "I didn't understand the request format. Please ask about weather in a specific city.",
                "stop_reason": "end_turn"
            }
        
        print(f"ðŸ“¤ Sending response: {json.dumps(response, indent=2)}")
        return jsonify(response), 200
        
    except Exception as e:
        print(f"âŒ Error processing request: {str(e)}")
        print(f"âŒ Request data: {request.data}")
        print(f"âŒ Request content type: {request.content_type}")
        
        error_response = {
            "completion": f"Sorry, I encountered an error: {str(e)}",
            "stop_reason": "end_turn"
        }
        return jsonify(error_response), 200

def extract_city_from_message(message):
    """Extract city name from user message"""
    
    # Simple city extraction logic
    words = message.split()
    
    # Look for patterns like "weather in NYC", "forecast for London"
    for i, word in enumerate(words):
        if word.lower() in ['in', 'for'] and i + 1 < len(words):
            city = words[i + 1].replace('?', '').replace(',', '').replace('.', '')
            return city
    
    # Look for common city abbreviations and expand them
    city_mappings = {
        'nyc': 'New York City',
        'ny': 'New York',
        'la': 'Los Angeles',
        'sf': 'San Francisco',
        'dc': 'Washington DC',
        'chi': 'Chicago',
        'boston': 'Boston',
        'miami': 'Miami',
        'seattle': 'Seattle'
    }
    
    for word in words:
        clean_word = word.lower().replace('?', '').replace(',', '').replace('.', '')
        if clean_word in city_mappings:
            return city_mappings[clean_word]
        # Also check if it's already a proper city name
        if len(clean_word) > 2 and clean_word.isalpha():
            return word.replace('?', '').replace(',', '').replace('.', '')
    
    # Default fallback
    return "New York City"

@app.route('/ping', methods=['GET'])
def ping():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/health', methods=['GET'])
def health():
    """Detailed health check with configuration"""
    
    config_status = {
        "status": "healthy",
        "gateway_url_configured": bool(GATEWAY_URL and GATEWAY_URL != 'YOUR_GATEWAY_URL_HERE'),
        "oauth_token_configured": bool(OAUTH_TOKEN and OAUTH_TOKEN != 'YOUR_OAUTH_TOKEN_HERE'),
        "aws_region": AWS_REGION,
        "weather_tool_name": WEATHER_TOOL_NAME,
        "gateway_url": GATEWAY_URL if GATEWAY_URL != 'YOUR_GATEWAY_URL_HERE' else "NOT_CONFIGURED",
        "oauth_token_preview": OAUTH_TOKEN[:20] + "..." if OAUTH_TOKEN and OAUTH_TOKEN != 'YOUR_OAUTH_TOKEN_HERE' else "NOT_CONFIGURED"
    }
    
    return jsonify(config_status), 200

@app.route('/test', methods=['GET'])
def test_tool():
    """Test endpoint to verify tool calling works"""
    
    test_city = "London"
    print(f"ðŸ§ª Testing weather tool with city: {test_city}")
    
    try:
        result = get_weather(test_city)
        return jsonify({
            "test_city": test_city,
            "result": result,
            "tool_name": WEATHER_TOOL_NAME,
            "status": "success"
        }), 200
    except Exception as e:
        return jsonify({
            "test_city": test_city,
            "error": str(e),
            "tool_name": WEATHER_TOOL_NAME,
            "status": "error"
        }), 500

if __name__ == '__main__':
    print("Starting Weather Agent with myWeatherTool Integration on port 8080...")
    print(f"Gateway URL: {GATEWAY_URL}")
    print(f"OAuth Token: {'âœ… Configured' if OAUTH_TOKEN and OAUTH_TOKEN != 'YOUR_OAUTH_TOKEN_HERE' else 'âŒ Missing'}")
    print(f"AWS Region: {AWS_REGION}")
    print(f"Weather Tool Name: {WEATHER_TOOL_NAME}")
    
    # Validate configuration
    if not GATEWAY_URL or GATEWAY_URL == 'YOUR_GATEWAY_URL_HERE':
        print("âš ï¸  WARNING: GATEWAY_URL not configured!")
    
    if not OAUTH_TOKEN or OAUTH_TOKEN == 'YOUR_OAUTH_TOKEN_HERE':
        print("âš ï¸  WARNING: OAUTH_TOKEN not configured!")
    
    print("\nðŸ”§ Available endpoints:")
    print("  POST /invocations - Main agent endpoint")
    print("  GET  /ping       - Health check")
    print("  GET  /health     - Detailed health check")
    print("  GET  /test       - Test weather tool")
    
    app.run(host='0.0.0.0', port=8080, debug=True)