"""
Demo 4 — Strands + Memory + Gateway + Identity (OAuth minted at runtime).

Identity replaces baked GATEWAY_TOKEN. Falls back to GATEWAY_TOKEN if Identity fails.

    agentcore configure -e strands_agent_identity.py -n strands_agent_identity \
      --disable-memory --non-interactive --region us-east-1
    agentcore deploy -a strands_agent_identity \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --env GATEWAY_URL="$GATEWAY_URL" \
      --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
      --env IDENTITY_AUTH_FLOW=M2M \
      --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
      --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
      --auto-update-on-conflict
"""


from __future__ import annotations

import os

from dotenv import load_dotenv
from strands import Agent

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    FAQ_TOOLS,
    SUPPORT_SYSTEM_PROMPT,
    build_memory_session_manager,
    build_model,
    fetch_identity_token,
    load_gateway_mcp_tools,
    session_ids,
    strands_text,
)

load_dotenv()
app = BedrockAgentCoreApp()
model = build_model()
PROVIDER = os.getenv("IDENTITY_PROVIDER_NAME", "gateway-cognito-m2m")


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    print("IDENTITY_PROVIDER_NAME:", PROVIDER)

    query = payload.get("prompt", "No prompt found in input")
    actor_id, session_id = session_ids(payload, context)
    session_manager = build_memory_session_manager(actor_id, session_id)

    tools = list(FAQ_TOOLS)
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    token = os.getenv("GATEWAY_TOKEN", "").strip()
    mcp_client = None

    try:
        try:
            token = fetch_identity_token()
            print("Identity token acquired")
        except Exception as exc:  # noqa: BLE001
            print(f"Identity token fetch failed ({exc}); using GATEWAY_TOKEN fallback if set")

        if gateway_url and token:
            mcp_client, mcp_tools = load_gateway_mcp_tools(gateway_url, token)
            tools = tools + list(mcp_tools)
        else:
            print("No Gateway auth — FAQ tools only")

        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=SUPPORT_SYSTEM_PROMPT
            + "\nGateway tools are authenticated via AgentCore Identity when available.",
            session_manager=session_manager,
            agent_id="strands_support_identity",
        )
        result = agent(query)
        text = strands_text(result)
        return {"result": text, "actor_id": actor_id, "thread_id": session_id}
    finally:
        if mcp_client is not None:
            try:
                mcp_client.__exit__(None, None, None)
            except Exception as exc:  # noqa: BLE001
                print(f"MCP client stop warning: {exc}")


if __name__ == "__main__":
    app.run()
