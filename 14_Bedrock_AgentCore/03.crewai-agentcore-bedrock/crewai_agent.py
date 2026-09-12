"""
Demo 1 — CrewAI on AgentCore Runtime only (single-agent crew).

    agentcore configure -e crewai_agent.py -n crewai_agent \
      --deployment-type container --disable-memory --non-interactive \
      --region us-east-1 --requirements-file requirements-runtime.txt
    agentcore deploy -a crewai_agent \
      --env AWS_REGION=us-east-1 \
      --env OPENAI_API_KEY="$OPENAI_API_KEY" \
      --env CREWAI_DISABLE_TELEMETRY=true \
      --auto-update-on-conflict
    agentcore invoke -a crewai_agent \
      '{"prompt":"Summarize Amazon Bedrock AgentCore in 5 short bullets"}'
"""


from __future__ import annotations

from dotenv import load_dotenv

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import build_llm, build_single_agent_crew, web_search

load_dotenv()
app = BedrockAgentCoreApp()
llm = build_llm()


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    topic = payload.get("prompt") or payload.get("topic") or "Artificial Intelligence"
    crew = build_single_agent_crew(llm, tools=[web_search])
    result = crew.kickoff(inputs={"topic": topic})
    text = getattr(result, "raw", None) or str(result)
    return {"result": text}


if __name__ == "__main__":
    app.run()
