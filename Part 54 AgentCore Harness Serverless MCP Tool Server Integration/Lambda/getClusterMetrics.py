import json

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except Exception:
        body = event
        
    method = body.get('method')
    request_id = body.get('id', 1)

    # 1. Handle Protocol Initialization Handshake
    if method == "initialize":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {} 
                    },
                    "serverInfo": {
                        "name": "cluster-ops-server",
                        "version": "1.0.0"
                    }
                }
            })
        }

    # 2. Handle Tool Discovery Schema Registration
    elif method == "tools/list":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "getClusterMetrics",
                            "description": "Fetches live cluster metrics for prod-ops-cluster including nodes, CPU, RAM, RPS and cost.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    ]
                }
            })
        }

    # 3. Handle Tool Execution Runtime
    elif method == "tools/call":
        params = body.get('params', {})
        tool_name = params.get('name')
        
        if tool_name == "getClusterMetrics":
            metrics_payload = {
                "cluster_name": "prod-ops-cluster",
                "nodes": 6,
                "vcpus_per_node": 16,
                "ram_per_node_gb": 64,
                "avg_cpu_utilization": 72,
                "avg_ram_utilization": 58,
                "rps_per_node": 420,
                "node_cost_monthly": 180
            }
            
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(metrics_payload)
                            }
                        ]
                    }
                })
            }
        
    return {
        "statusCode": 200,
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method/Tool not found: {method}"}
        })
    }
