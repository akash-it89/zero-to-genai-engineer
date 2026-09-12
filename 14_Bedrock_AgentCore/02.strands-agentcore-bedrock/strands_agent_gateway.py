"""
Demo 3 — Strands + Memory + Gateway MCP (baked Cognito JWT).

Requires GATEWAY_URL + GATEWAY_TOKEN (mint with scripts/get_gateway_token.py).
Reuse Gateway from 01.langraph-agentcore-bedrock when possible.

    export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py \
      --credentials gateway-credentials.json)"
    export GATEWAY_URL="$(.venv/bin/python -c 'import json;from pathlib import Path;print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])')"

    agentcore configure -e strands_agent_gateway.py -n strands_agent_gateway \
      --disable-memory --non-interactive --region us-east-1
    agentcore deploy -a strands_agent_gateway \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --env GATEWAY_URL="$GATEWAY_URL" \
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
    load_gateway_mcp_tools,
    session_ids,
    strands_text,
)

load_dotenv()
app = BedrockAgentCoreApp()
model = build_model()


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    query = payload.get("prompt", "No prompt found in input")
    actor_id, session_id = session_ids(payload, context)
    session_manager = build_memory_session_manager(actor_id, session_id)

    tools = list(FAQ_TOOLS)
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    gateway_token = os.getenv("GATEWAY_TOKEN", "").strip()
    mcp_client = None

    try:
        if gateway_url and gateway_token:
            mcp_client, mcp_tools = load_gateway_mcp_tools(gateway_url, gateway_token)
            tools = tools + list(mcp_tools)
        else:
            print("GATEWAY_URL/TOKEN missing — FAQ tools only")

        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=SUPPORT_SYSTEM_PROMPT
            + "\nYou may also call Gateway MCP tools (weather/time) when useful.",
            session_manager=session_manager,
            agent_id="strands_support_gateway",
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
