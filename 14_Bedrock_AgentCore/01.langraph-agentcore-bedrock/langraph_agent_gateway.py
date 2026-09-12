"""
Demo: AgentCore Runtime + Memory + Gateway (MCP tools).

Requires:
  MEMORY_ID          — e.g. memorybot-w6GzC7D97L
  GATEWAY_URL        — AgentCore Gateway MCP endpoint URL
  GATEWAY_TOKEN      — Bearer token for the gateway (Cognito / M2M), OR leave empty
                       and set USE_FAQ_FALLBACK=1 to run with local FAQ tools only

Create a gateway first:
  agentcore create_mcp_gateway --name lauki-gateway --region us-west-2
  agentcore create_mcp_gateway_target ...

Configure & launch:
  agentcore configure -e langraph_agent_gateway.py -n langraph_agent_gateway
  agentcore launch --env OPENAI_API_KEY=... --env MEMORY_ID=memorybot-w6GzC7D97L \
    --env GATEWAY_URL=https://... --env GATEWAY_TOKEN=...
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain.agents import create_agent

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    FAQ_TOOLS,
    MEMORY_ID,
    MemoryMiddleware,
    build_memory,
    build_model,
    load_gateway_mcp_tools,
    memory_config,
)

load_dotenv()
app = BedrockAgentCoreApp()

checkpointer, store = build_memory()
model = build_model()


def build_tools():
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    gateway_token = os.getenv("GATEWAY_TOKEN", "").strip()
    if gateway_url and gateway_token:
        try:
            mcp_tools = load_gateway_mcp_tools(gateway_url, gateway_token)
            if mcp_tools:
                print(f"Using {len(mcp_tools)} Gateway MCP tools (+ local FAQ)")
                return FAQ_TOOLS + mcp_tools
        except Exception as exc:  # noqa: BLE001
            print(f"Gateway MCP load failed ({exc}); falling back to FAQ tools")
    else:
        print("GATEWAY_URL/GATEWAY_TOKEN not set — FAQ tools only")
    return FAQ_TOOLS


tools = build_tools()

system_prompt = """You are a helpful assistant with FAQ search and optional Gateway MCP tools.

Guidelines:
1. Prefer Gateway MCP tools when they match the user request.
2. Use search_faq / search_detailed_faq for Lauki phone product questions.
3. Remember prior turns via memory when actor_id/thread_id are provided.
4. Be concise and cite tool results.
"""

agent = create_agent(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
    store=store,
    middleware=[MemoryMiddleware()],
    system_prompt=system_prompt,
)


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    print("MEMORY_ID:", MEMORY_ID)
    print("GATEWAY_URL set:", bool(os.getenv("GATEWAY_URL")))

    query = payload.get("prompt", "No prompt found in input")
    cfg = memory_config(payload, context)
    result = agent.invoke(
        {"messages": [("human", query)]},
        config={"configurable": cfg["configurable"]},
    )
    answer = result["messages"][-1].content
    return {
        "result": answer,
        "actor_id": cfg["actor_id"],
        "thread_id": cfg["thread_id"],
        "memory_id": MEMORY_ID,
        "demo": "runtime+memory+gateway",
    }


if __name__ == "__main__":
    app.run()
