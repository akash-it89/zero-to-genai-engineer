"""
Demo 2 — Strands + AgentCore Memory (actor_id + thread_id / session_id).

Same support tools as Demo 1, plus AgentCoreMemorySessionManager.

    agentcore configure -e strands_agent_memory.py -n strands_agent_memory \
      --disable-memory --non-interactive --region us-east-1
    agentcore deploy -a strands_agent_memory \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --auto-update-on-conflict

    agentcore invoke -a strands_agent_memory \
      '{"prompt":"My name is Mohamed and I like concise answers","actor_id":"mohamed","thread_id":"demo-1"}'
    agentcore invoke -a strands_agent_memory \
      '{"prompt":"What is my name and preference?","actor_id":"mohamed","thread_id":"demo-1"}'
"""


from __future__ import annotations

from dotenv import load_dotenv
from strands import Agent

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    FAQ_TOOLS,
    MEMORY_ID,
    SUPPORT_SYSTEM_PROMPT,
    build_memory_session_manager,
    build_model,
    session_ids,
    strands_text,
)

load_dotenv()
app = BedrockAgentCoreApp()
model = build_model()


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    print("MEMORY_ID:", MEMORY_ID)

    query = payload.get("prompt", "No prompt found in input")
    actor_id, session_id = session_ids(payload, context)
    session_manager = build_memory_session_manager(actor_id, session_id)

    agent = Agent(
        model=model,
        tools=FAQ_TOOLS,
        system_prompt=SUPPORT_SYSTEM_PROMPT
        + "\nRemember user details from prior turns in this session.",
        session_manager=session_manager,
        agent_id="strands_support_memory",
    )
    result = agent(query)
    text = strands_text(result)
    print("Result:", text[:500])
    return {"result": text, "actor_id": actor_id, "thread_id": session_id}


if __name__ == "__main__":
    app.run()
