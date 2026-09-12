"""
Demo 3 — CrewAI + Memory + Gateway MCP tools (baked JWT).

    export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py \
      --credentials gateway-credentials.json)"
    export GATEWAY_URL="$(.venv/bin/python -c 'import json;from pathlib import Path;print(json.loads(Path("gateway-credentials.json").read_text())["gateway"]["gatewayUrl"])')"

    agentcore configure -e crewai_agent_gateway.py -n crewai_agent_gateway \
      --deployment-type container --disable-memory --non-interactive \
      --region us-east-1 --requirements-file requirements-runtime.txt
    agentcore deploy -a crewai_agent_gateway \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --env GATEWAY_URL="$GATEWAY_URL" \
      --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
      --env CREWAI_DISABLE_TELEMETRY=true \
      --auto-update-on-conflict
"""


from __future__ import annotations

import os

from dotenv import load_dotenv

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    build_brief_crew,
    build_llm,
    load_gateway_tools_as_crewai,
    load_memory_context,
    save_memory_turn,
    session_ids,
    web_search,
)

load_dotenv()
app = BedrockAgentCoreApp()
llm = build_llm()


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    topic = payload.get("prompt") or payload.get("topic") or "AI agents"
    actor_id, session_id = session_ids(payload, context)
    memory_context = load_memory_context(actor_id, session_id)

    tools = [web_search]
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    gateway_token = os.getenv("GATEWAY_TOKEN", "").strip()
    if gateway_url and gateway_token:
        try:
            tools = tools + load_gateway_tools_as_crewai(gateway_url, gateway_token)
        except Exception as exc:  # noqa: BLE001
            print(f"Gateway load failed: {exc}")
    else:
        print("GATEWAY_URL/TOKEN missing — web_search only")

    crew = build_brief_crew(llm, tools=tools, memory_context=memory_context)
    result = crew.kickoff(inputs={"topic": topic})
    text = getattr(result, "raw", None) or str(result)
    save_memory_turn(actor_id, session_id, topic, text)
    return {"result": text, "actor_id": actor_id, "thread_id": session_id}


if __name__ == "__main__":
    app.run()
