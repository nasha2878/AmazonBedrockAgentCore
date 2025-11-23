from bedrock_agentcore.memory import MemoryClient

# --- Configuration ---
MEMORY_ID = "memltm-7CYKwqCwxE" #REPLACE WITH YOUR MEMORY ID
SESSION_ID = "default_session"  # OR YOUR CURRENT SESSION ID FOR SUMMARIZATION STRATEGY
memory_client = MemoryClient(region_name="us-east-1")

# --- Step 1: Discover strategies ---
strategies = memory_client.get_memory_strategies(memory_id=MEMORY_ID)

namespaces = []
for s in strategies:
    stype = s.get("type")
    sid = s.get("strategyId") or s.get("id")
    if not sid:
        continue
    if stype == "SUMMARIZATION":
        ns = f"/strategies/{sid}/actors/USER/sessions/{SESSION_ID}"
    else:
        ns = f"/strategies/{sid}/actors/USER"
    namespaces.append((stype, ns))

print("Active strategies and namespaces:")
for stype, ns in namespaces:
    print(f"- {stype}: {ns}")

# --- Step 2: Dump all memories from each namespace ---
for stype, ns in namespaces:
    print(f"\nStrategy: {stype} | Namespace: {ns}")
    try:
        # Use wildcard query to fetch everything
        memories = memory_client.retrieve_memories(
            memory_id=MEMORY_ID,
            namespace=ns,
            query="*"
        )
        if memories:
            for m in memories:
                print("  ", m)
        else:
            print("   No memories found.")
    except Exception as e:
        print("   Error:", e)
