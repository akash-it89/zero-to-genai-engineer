"""
Demo: AgentCore Runtime + Memory + Gateway + Identity.

Uses @requires_access_token (AgentCore Identity) to obtain an OAuth token,
then calls AgentCore Gateway MCP tools with that token.

Requires:
  MEMORY_ID
  GATEWAY_URL
  IDENTITY_PROVIDER_NAME  — OAuth2 credential provider name in AgentCore Identity
  IDENTITY_SCOPES         — comma-separated scopes (optional)
  IDENTITY_AUTH_FLOW      — M2M (default) | USER_FEDERATION | ON_BEHALF_OF_TOKEN_EXCHANGE

Configure & launch:
  agentcore configure -e langraph_agent_identity.py -n langraph_agent_identity
  agentcore launch --env OPENAI_API_KEY=... --env MEMORY_ID=memorybot-w6GzC7D97L \
    --env GATEWAY_URL=https://... \
    --env IDENTITY_PROVIDER_NAME=my-gateway-oauth-provider \
    --env IDENTITY_AUTH_FLOW=M2M
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain.agents import create_agent

from bedrock_agentcore.identity.auth import requires_access_token
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

PROVIDER = os.getenv("IDENTITY_PROVIDER_NAME", "gateway-oauth-provider")
SCOPES = [s.strip() for s in os.getenv("IDENTITY_SCOPES", "").split(",") if s.strip()]
AUTH_FLOW = os.getenv("IDENTITY_AUTH_FLOW", "M2M")  # type: ignore[assignment]


@requires_access_token(
    provider_name=PROVIDER,
    scopes=SCOPES,
    auth_flow=AUTH_FLOW,  # type: ignore[arg-type]
    into="access_token",
)
def fetch_identity_token(*, access_token: str) -> str:
    """Fetch OAuth access token via AgentCore Identity (injected by decorator)."""
    return access_token


def build_tools():
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    tools = list(FAQ_TOOLS)

    if not gateway_url:
        print("GATEWAY_URL not set — FAQ tools only")
        return tools

    # Prefer Identity token; fall back to static GATEWAY_TOKEN for local testing
    token = os.getenv("GATEWAY_TOKEN", "").strip()
    try:
        token = fetch_identity_token()
        print(f"Identity token acquired via provider={PROVIDER} flow={AUTH_FLOW}")
    except Exception as exc:  # noqa: BLE001
        print(f"Identity token fetch failed ({exc}); using GATEWAY_TOKEN fallback if set")

    if gateway_url and token:
        try:
            mcp_tools = load_gateway_mcp_tools(gateway_url, token)
            tools.extend(mcp_tools)
            print(f"Loaded {len(mcp_tools)} Gateway tools with Identity")
        except Exception as exc:  # noqa: BLE001
            print(f"Gateway MCP load failed: {exc}")
    return tools


tools = build_tools()

system_prompt = """You are a secure FAQ / tooling assistant.

You may use local FAQ tools and Gateway MCP tools authenticated via AgentCore Identity.
Prefer authenticated Gateway tools for external systems. Be concise and accurate.
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
    print("IDENTITY_PROVIDER_NAME:", PROVIDER)

    # Refresh gateway tools each invoke so Identity token stays valid
    global agent, tools
    tools = build_tools()
    agent = create_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        store=store,
        middleware=[MemoryMiddleware()],
        system_prompt=system_prompt,
    )

    query = payload.get("prompt", "No prompt found in input")
    cfg = memory_config(payload, context)
    result = agent.invoke(
        {"messages": [("human", query)]},
        config={"configurable": cfg["configurable"]},
    )
    return {
        "result": result["messages"][-1].content,
        "actor_id": cfg["actor_id"],
        "thread_id": cfg["thread_id"],
        "memory_id": MEMORY_ID,
        "identity_provider": PROVIDER,
        "demo": "runtime+memory+gateway+identity",
    }


if __name__ == "__main__":
    app.run()
