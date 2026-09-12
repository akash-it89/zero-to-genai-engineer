"""
Demo 4 — CrewAI + Memory + Gateway + Identity.

    agentcore configure -e crewai_agent_identity.py -n crewai_agent_identity \
      --deployment-type container --disable-memory --non-interactive \
      --region us-east-1 --requirements-file requirements-runtime.txt
    agentcore deploy -a crewai_agent_identity \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --env GATEWAY_URL="$GATEWAY_URL" \
      --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
      --env IDENTITY_AUTH_FLOW=M2M \
      --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
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
    fetch_identity_token,
    load_gateway_tools_as_crewai,
    load_memory_context,
    save_memory_turn,
    session_ids,
    web_search,
)

load_dotenv()
app = BedrockAgentCoreApp()
llm = build_llm()
PROVIDER = os.getenv("IDENTITY_PROVIDER_NAME", "gateway-cognito-m2m")


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    print("IDENTITY_PROVIDER_NAME:", PROVIDER)
    topic = payload.get("prompt") or payload.get("topic") or "AI agents"
    actor_id, session_id = session_ids(payload, context)
    memory_context = load_memory_context(actor_id, session_id)

    tools = [web_search]
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    token = os.getenv("GATEWAY_TOKEN", "").strip()
    try:
        token = fetch_identity_token()
        print("Identity token acquired")
    except Exception as exc:  # noqa: BLE001
        print(f"Identity failed ({exc}); GATEWAY_TOKEN fallback if set")

    if gateway_url and token:
        try:
            tools = tools + load_gateway_tools_as_crewai(gateway_url, token)
        except Exception as exc:  # noqa: BLE001
            print(f"Gateway load failed: {exc}")

    crew = build_brief_crew(llm, tools=tools, memory_context=memory_context)
    result = crew.kickoff(inputs={"topic": topic})
    text = getattr(result, "raw", None) or str(result)
    save_memory_turn(actor_id, session_id, topic, text)
    return {"result": text, "actor_id": actor_id, "thread_id": session_id}


if __name__ == "__main__":
    app.run()
