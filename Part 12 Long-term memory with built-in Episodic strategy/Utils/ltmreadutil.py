from bedrock_agentcore.memory import MemoryClient

# --- Configuration ---
MEMORY_ID = "memory_c2twc-GEY9XWG6GL"   # REPLACE memory_c2twc-GEY9XWG6GL WITH YOUR MEMORY ID
SESSION_ID = "default_session"    # For summarization + episodic 
memory_client = MemoryClient(region_name="us-east-1")

# --- Step 1: Discover strategies ---
strategies = memory_client.get_memory_strategies(memory_id=MEMORY_ID)

namespaces = []

for s in strategies:
    stype = s.get("type")
    sid = s.get("strategyId") or s.get("id")
    if not sid:
        continue

    # --- Summarization strategy (session-scoped) ---
    if stype == "SUMMARIZATION":
        ns = f"/strategies/{sid}/actors/USER/sessions/{SESSION_ID}"
        namespaces.append((f"{stype} (summary)", ns))

    # --- Episodic strategy (two namespaces!) ---
    elif stype == "EPISODIC":
        # Episodes (session-scoped)
        epi_episode_ns = f"/strategies/{sid}/actors/USER/sessions/{SESSION_ID}"
        namespaces.append((f"{stype} (episodes)", epi_episode_ns))

        # Reflections (actor-scoped)
        epi_reflection_ns = f"/strategies/{sid}/actors/USER"
        namespaces.append((f"{stype} (reflections)", epi_reflection_ns))

    # --- All other durable strategies (semantic, preference, etc.) ---
    else:
        ns = f"/strategies/{sid}/actors/USER"
        namespaces.append((stype, ns))

# --- Print discovered namespaces ---
print("Active strategies and namespaces:")
for stype, ns in namespaces:
    print(f"- {stype}: {ns}")

# --- Step 2: Dump all memories from each namespace ---
for stype, ns in namespaces:
    print(f"\nStrategy: {stype} | Namespace: {ns}")
    try:
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
