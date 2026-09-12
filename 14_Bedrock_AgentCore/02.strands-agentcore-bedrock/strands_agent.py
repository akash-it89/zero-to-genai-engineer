"""
Demo 1 — Strands Support Copilot on AgentCore Runtime only (no Memory / Gateway).

    agentcore configure -e strands_agent.py -n strands_agent \
      --disable-memory --non-interactive --region us-east-1
    agentcore deploy -a strands_agent \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --auto-update-on-conflict
    agentcore invoke -a strands_agent \
      '{"prompt": "How do I activate a new SIM?"}'
"""

from __future__ import annotations

from dotenv import load_dotenv
from strands import Agent

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import FAQ_TOOLS, SUPPORT_SYSTEM_PROMPT, build_model, strands_text

load_dotenv()
app = BedrockAgentCoreApp()

agent = Agent(
    model=build_model(),
    tools=FAQ_TOOLS,
    system_prompt=SUPPORT_SYSTEM_PROMPT,
)


@app.entrypoint
def invoke(payload, context):
    """Runtime-only invoke — no Memory session manager."""
    query = payload.get("prompt", "No prompt found in input")
    print("User Query:", query)
    result = agent(query)
    return strands_text(result)


if __name__ == "__main__":
    app.run()
