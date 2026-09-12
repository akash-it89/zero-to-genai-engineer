"""
Demo 2 — CrewAI + AgentCore Memory (prior briefs/preferences injected into tasks).

    agentcore configure -e crewai_agent_memory.py -n crewai_agent_memory \
      --deployment-type container --disable-memory --non-interactive \
      --region us-east-1 --requirements-file requirements-runtime.txt
    agentcore deploy -a crewai_agent_memory \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env MEMORY_ID="$MEMORY_ID" \
      --env CREWAI_DISABLE_TELEMETRY=true \
      --auto-update-on-conflict

    agentcore invoke -a crewai_agent_memory \
      '{"prompt":"I prefer concise bullet briefs","actor_id":"mohamed","thread_id":"brief-1"}'
    agentcore invoke -a crewai_agent_memory \
      '{"prompt":"Compare Strands vs LangGraph on AgentCore","actor_id":"mohamed","thread_id":"brief-1"}'
"""


from __future__ import annotations

from dotenv import load_dotenv

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    build_brief_crew,
    build_llm,
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

    crew = build_brief_crew(llm, tools=[web_search], memory_context=memory_context)
    result = crew.kickoff(inputs={"topic": topic})
    text = getattr(result, "raw", None) or str(result)
    save_memory_turn(actor_id, session_id, topic, text)
    return {"result": text, "actor_id": actor_id, "thread_id": session_id}


if __name__ == "__main__":
    app.run()
