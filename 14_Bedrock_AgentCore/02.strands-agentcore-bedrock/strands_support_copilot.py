"""
Demo 5 — Flagship Lauki Support Copilot (Memory + Gateway + Identity + web_search).

    agentcore configure -e strands_support_copilot.py -n strands_support_copilot \
      --disable-memory --non-interactive --region us-east-1
    agentcore deploy -a strands_support_copilot \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --env GATEWAY_URL="$GATEWAY_URL" \
      --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \
      --env IDENTITY_AUTH_FLOW=M2M \
      --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \
      --env GATEWAY_TOKEN="$GATEWAY_TOKEN" \
      --auto-update-on-conflict

Then open Streamlit:
    export SUPPORT_RUNTIME_ARN=...
    streamlit run streamlit_support_app.py
"""


from __future__ import annotations

import os

from dotenv import load_dotenv
from strands import Agent

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    SUPPORT_SYSTEM_PROMPT,
    SUPPORT_TOOLS,
    apply_bedrock_guardrail,
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


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    query = payload.get("prompt", "No prompt found in input")
    actor_id, session_id = session_ids(payload, context)

    # Bedrock Guardrail on INPUT (works even when LLM is OpenAI)
    safe_query, blocked = apply_bedrock_guardrail(str(query), source="INPUT")
    if blocked:
        print("Guardrail intervened on INPUT")
        return {
            "result": safe_query,
            "actor_id": actor_id,
            "thread_id": session_id,
            "guardrail": "intervened_input",
        }
    query = safe_query

    session_manager = build_memory_session_manager(actor_id, session_id)

    tools = list(SUPPORT_TOOLS)
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    token = os.getenv("GATEWAY_TOKEN", "").strip()
    mcp_client = None

    try:
        try:
            token = fetch_identity_token()
            print("Identity token acquired")
        except Exception as exc:  # noqa: BLE001
            print(f"Identity failed ({exc}); GATEWAY_TOKEN fallback if set")

        if gateway_url and token:
            mcp_client, mcp_tools = load_gateway_mcp_tools(gateway_url, token)
            tools = tools + list(mcp_tools)

        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=SUPPORT_SYSTEM_PROMPT
            + "\nYou are the full Support Copilot: FAQ + web + Gateway + Memory.",
            session_manager=session_manager,
            agent_id="strands_support_copilot",
        )
        result = agent(query)
        text = strands_text(result)
        text, out_blocked = apply_bedrock_guardrail(text, source="OUTPUT")
        if out_blocked:
            print("Guardrail intervened on OUTPUT")
        return {
            "result": text,
            "actor_id": actor_id,
            "thread_id": session_id,
            "guardrail": "intervened_output" if out_blocked else "passed",
        }
    finally:
        if mcp_client is not None:
            try:
                mcp_client.__exit__(None, None, None)
            except Exception as exc:  # noqa: BLE001
                print(f"MCP client stop warning: {exc}")


if __name__ == "__main__":
    app.run()
