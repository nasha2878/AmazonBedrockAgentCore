# Save as streaming_agentcore_client.py
import boto3
import json

def invoke_agentcore_runtime(message):
    """Invoke AgentCore runtime and handle streaming response"""
    
    print(f"🤖 Invoking AgentCore Runtime")
    print(f"   Message: {message}")
    
    try:
        client = boto3.client('bedrock-agentcore', region_name='us-east-1')
        
        response = client.invoke_agent_runtime(
            agentRuntimeArn="<<AGENT RUNTIME ARN>>", #REPLACE WITH YOUR AGENT'S RUNTIME ARN
            payload=json.dumps({
                "input": {
                    "text": message
                }
            })
        )
        
        print(f"✅ Success!")
        print(f"📥 Status Code: {response['statusCode']}")
        print(f"📥 Content Type: {response['contentType']}")
        print(f"📥 Session ID: {response['runtimeSessionId']}")
        
        # Read the streaming body
        if 'response' in response:
            streaming_body = response['response']
            
            # Read all the data from the stream
            response_data = streaming_body.read()
            
            # Decode if it's bytes
            if isinstance(response_data, bytes):
                response_text = response_data.decode('utf-8')
            else:
                response_text = response_data
            
            print(f"🎯 Raw Response Data: {response_text}")
            
            # Try to parse as JSON
            try:
                parsed_response = json.loads(response_text)
                print(f"🎯 Parsed Response: {json.dumps(parsed_response, indent=2)}")
                
                # Look for common response fields
                for key in ['completion', 'output', 'result', 'response', 'text', 'message']:
                    if key in parsed_response:
                        agent_response = parsed_response[key]
                        print(f"🤖 Agent Response: {agent_response}")
                        return agent_response
                
                # If no standard field, return the whole parsed response
                return parsed_response
                
            except json.JSONDecodeError:
                # If not JSON, return as text
                print(f"🤖 Agent Response (text): {response_text}")
                return response_text
        
        return "No response data found"
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def interactive_chat():
    """Interactive chat with proper streaming support"""
    
    print(f"\n💬 AgentCore Interactive Chat (Streaming)")
    print("="*50)
    print("Type 'quit' to exit")
    
    while True:
        try:
            message = input("\n🧑 You: ").strip()
            
            if message.lower() in ['quit', 'exit', 'bye']:
                print("👋 Goodbye!")
                break
            
            if not message:
                continue
            
            print(f"\n{'='*50}")
            response = invoke_agentcore_runtime(message)
            print(f"{'='*50}")
            
            if response:
                print(f"\n🤖 Final Answer: {response}")
            else:
                print(f"❌ No response received")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def quick_test():
    """Quick test of different message types"""
    
    print(f"🧪 Quick Test Suite")
    print("="*30)
    
    test_messages = [
        "What is the weather in NYC?",
        "How about London weather?",
        "Get me the weather in Chicago"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n🧪 Test {i}: {message}")
        print("-" * 40)
        
        response = invoke_agentcore_runtime(message)
        
        if response:
            print(f"✅ Success: {response}")
        else:
            print(f"❌ Failed")
        
        if i < len(test_messages):
            input("\nPress Enter for next test...")

if __name__ == "__main__":
    print("🎉 AgentCore Python Client - Working!")
    print("="*50)
    
    choice = input("Choose:\n1. Interactive chat\n2. Quick test suite\n3. Single test\nEnter 1, 2, or 3: ").strip()
    
    if choice == "1":
        interactive_chat()
    elif choice == "2":
        quick_test()
    elif choice == "3":
        message = input("Enter your message: ").strip()
        if message:
            response = invoke_agentcore_runtime(message)
            print(f"\n🎯 Final Response: {response}")
    else:
        print("Invalid choice. Starting interactive chat...")
        interactive_chat()