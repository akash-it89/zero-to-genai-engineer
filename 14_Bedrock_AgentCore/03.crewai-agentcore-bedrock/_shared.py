"""Shared helpers for CrewAI + AgentCore demos."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from crewai import LLM
from crewai.tools import tool

load_dotenv()

# Avoid CrewAI telemetry fighting AgentCore OTEL in Runtime containers
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

REGION = (os.getenv("AWS_REGION") or "us-east-1").strip()
MEMORY_ID = (os.getenv("MEMORY_ID") or "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


def build_llm() -> LLM:
    """Prefer OpenAI; Bedrock fallback for accounts with model access."""
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        print(f"Using CrewAI LLM openai/{OPENAI_MODEL}")
        return LLM(model=f"openai/{OPENAI_MODEL}", api_key=openai_key, temperature=0.3)
    print(f"Using CrewAI LLM bedrock/{BEDROCK_MODEL_ID}")
    return LLM(
        model=f"bedrock/{BEDROCK_MODEL_ID}",
        temperature=0.3,
        aws_region_name=REGION,
    )


def require_memory_id() -> str:
    if len(MEMORY_ID) < 12:
        raise RuntimeError(
            "MEMORY_ID is missing/too short. Pass --env MEMORY_ID=... at deploy.\n"
            f"Current MEMORY_ID={MEMORY_ID!r} REGION={REGION!r}"
        )
    return MEMORY_ID


def session_ids(payload: dict, context: Any) -> tuple[str, str]:
    actor_id = (payload.get("actor_id") or "default-user").strip()
    session_id = (
        payload.get("thread_id")
        or payload.get("session_id")
        or getattr(context, "session_id", None)
        or "default-session"
    )
    return actor_id, str(session_id).strip()


def memory_client():
    from bedrock_agentcore.memory import MemoryClient

    return MemoryClient(region_name=REGION)


def load_memory_context(actor_id: str, session_id: str, max_events: int = 8) -> str:
    """Pull recent short-term Memory events and format as text for the crew."""
    mem_id = require_memory_id()
    client = memory_client()
    try:
        events = client.list_events(
            memory_id=mem_id,
            actor_id=actor_id,
            session_id=session_id,
            max_results=max_events,
            include_payload=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Memory list_events failed: {exc}")
        return ""

    lines: list[str] = []
    for ev in events or []:
        payload = ev.get("payload") or ev.get("messages") or []
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    role = item.get("role") or item.get("Role") or "?"
                    text = item.get("content") or item.get("text") or item.get("Text") or str(item)
                    lines.append(f"{role}: {text}")
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    lines.append(f"{item[1]}: {item[0]}")
        else:
            lines.append(str(payload)[:500])
    if not lines:
        return ""
    return "Prior session notes:\n" + "\n".join(lines[-20:])


def save_memory_turn(actor_id: str, session_id: str, user_text: str, assistant_text: str) -> None:
    """Persist one user/assistant turn into AgentCore Memory STM."""
    mem_id = require_memory_id()
    client = memory_client()
    try:
        client.create_event(
            memory_id=mem_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[
                (user_text, "USER"),
                (assistant_text[:8000], "ASSISTANT"),
            ],
            event_timestamp=datetime.now(timezone.utc),
        )
        print("Saved turn to AgentCore Memory")
    except Exception as exc:  # noqa: BLE001
        print(f"Memory create_event failed: {exc}")


@tool("web_search")
def web_search(query: str) -> str:
    """Search the web for current market / competitor information."""
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    if tavily_key:
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=tavily_key)
            resp = client.search(query, max_results=4)
            bits = []
            for i, hit in enumerate(resp.get("results") or [], 1):
                bits.append(
                    f"{i}. {hit.get('title', '')}\n"
                    f"   {hit.get('content', '')}\n"
                    f"   Source: {hit.get('url', '')}"
                )
            return "\n".join(bits) if bits else "No results found."
        except Exception as exc:  # noqa: BLE001
            return f"Tavily search error: {exc}"
    try:
        from ddgs import DDGS

        results = DDGS().text(query, max_results=4)
        bits = []
        for i, hit in enumerate(results or [], 1):
            bits.append(
                f"{i}. {hit.get('title', '')}\n"
                f"   {hit.get('body', '')}\n"
                f"   Source: {hit.get('href', '')}"
            )
        return "\n".join(bits) if bits else "No results found."
    except Exception as exc:  # noqa: BLE001
        return f"Web search error: {exc}"


def load_gateway_tools_as_crewai(gateway_url: str, access_token: str) -> list:
    """Discover Gateway MCP tools and wrap each as a CrewAI @tool-compatible StructuredTool substitute."""
    import httpx
    from crewai.tools import tool as crew_tool

    url = gateway_url.rstrip("/")
    if not url.endswith("/mcp"):
        url = f"{url}/mcp"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    with httpx.Client(timeout=60.0) as client:
        list_resp = client.post(
            url,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        list_resp.raise_for_status()
        tools_meta = list_resp.json().get("result", {}).get("tools", [])

    wrapped = []
    for meta in tools_meta:
        mcp_name = meta["name"]
        description = meta.get("description") or f"MCP tool {mcp_name}"

        def _make(tool_name: str, tool_desc: str):
            @crew_tool(tool_name.replace("-", "_")[:64])
            def _runner(arguments_json: str = "{}") -> str:
                """Call an AgentCore Gateway MCP tool. Pass arguments as a JSON object string."""
                import json as _json

                try:
                    args = _json.loads(arguments_json) if arguments_json else {}
                except Exception:  # noqa: BLE001
                    args = {"input": arguments_json}
                with httpx.Client(timeout=120.0) as c:
                    r = c.post(
                        url,
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {"name": tool_name, "arguments": args},
                        },
                    )
                    r.raise_for_status()
                    result = r.json().get("result", {})
                    return _json.dumps(result, ensure_ascii=False)[:4000]

            _runner.description = tool_desc  # type: ignore[attr-defined]
            return _runner

        wrapped.append(_make(mcp_name, description))
    print(f"Gateway MCP tools wrapped for CrewAI: {[t.name for t in wrapped]}")
    return wrapped


def fetch_identity_token() -> str:
    from bedrock_agentcore.identity.auth import requires_access_token

    provider = os.getenv("IDENTITY_PROVIDER_NAME", "gateway-cognito-m2m")
    scopes = [s.strip() for s in os.getenv("IDENTITY_SCOPES", "").split(",") if s.strip()]
    auth_flow = os.getenv("IDENTITY_AUTH_FLOW", "M2M")

    @requires_access_token(
        provider_name=provider,
        scopes=scopes,
        auth_flow=auth_flow,  # type: ignore[arg-type]
        into="access_token",
    )
    def _fetch(*, access_token: str) -> str:
        return access_token

    return _fetch()


def build_brief_crew(llm: LLM, tools: list, memory_context: str = ""):
    """3-agent sequential competitor-brief crew."""
    from crewai import Agent, Crew, Process, Task

    ctx_block = f"\n\n{memory_context}\n" if memory_context else ""

    researcher = Agent(
        role="Market Researcher",
        goal="Gather current facts about the topic and named competitors",
        backstory=(
            "You are a sharp market researcher. You use web_search to find "
            "recent, credible information and cite sources briefly."
        ),
        llm=llm,
        tools=tools,
        verbose=True,
        allow_delegation=False,
        max_iter=4,
    )
    analyst = Agent(
        role="Competitive Analyst",
        goal="Compare strengths, weaknesses, and positioning",
        backstory=(
            "You turn raw research into a clear competitive analysis with "
            "bullets for strengths, gaps, and opportunities."
        ),
        llm=llm,
        tools=[],
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )
    writer = Agent(
        role="Brief Writer",
        goal="Produce a concise executive competitor brief",
        backstory=(
            "You write crisp one-page briefs for busy founders. "
            "No fluff. Clear sections and actionable takeaways."
        ),
        llm=llm,
        tools=[],
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    t_research = Task(
        description=(
            "Research this topic for a competitor brief: {topic}."
            f"{ctx_block}"
            "Use web_search. List key players, recent news, and differentiators."
        ),
        expected_output="Bullet research notes with short source URLs.",
        agent=researcher,
    )
    t_analyze = Task(
        description=(
            "Using the research notes, analyze competitive positioning for: {topic}."
            "Include strengths, weaknesses, and 3 opportunities."
        ),
        expected_output="Structured analysis with S/W/O bullets.",
        agent=analyst,
        context=[t_research],
    )
    t_write = Task(
        description=(
            "Write a one-page competitor brief for: {topic}."
            "Sections: Summary, Landscape, Comparison, Recommendations."
        ),
        expected_output="Markdown competitor brief ready to share.",
        agent=writer,
        context=[t_analyze],
    )

    return Crew(
        agents=[researcher, analyst, writer],
        tasks=[t_research, t_analyze, t_write],
        process=Process.sequential,
        verbose=True,
    )


def build_single_agent_crew(llm: LLM, tools: list):
    """Demo 1 baseline: one researcher agent."""
    from crewai import Agent, Crew, Process, Task

    researcher = Agent(
        role="Quick Researcher",
        goal="Answer the user prompt with a short researched summary",
        backstory="You research quickly and write clear summaries.",
        llm=llm,
        tools=tools,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )
    task = Task(
        description="Respond to this request using tools when helpful: {topic}",
        expected_output="A short researched answer.",
        agent=researcher,
    )
    return Crew(
        agents=[researcher],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
