"""
AgentCore Runtime: research agent via LangChain `create_agent` (ReAct under the hood).

NOTE: This is NOT a hand-built LangGraph StateGraph with your own nodes/edges.
`create_agent` uses a prebuilt agent loop. For an explicit graph (agent ↔ tools),
see `langgraph_research_graph_agentcore.py`. A frozen copy of this create_agent
entrypoint also lives in `research_create_agent_agentcore.py`.

Local tools: web_search, get_current_datetime, calculator, search_docs (RAG)
Gateway MCP (via Identity OAuth): get_weather, get_time, …

Configure & launch:
  agentcore configure -e langgraph_research_agentcore.py -n langgraph_research_agent
  agentcore launch -a langgraph_research_agent \\
    --env OPENAI_API_KEY=... \\
    --env MEMORY_ID=memorybot-w6GzC7D97L \\
    --env GATEWAY_URL=https://.../mcp \\
    --env IDENTITY_PROVIDER_NAME=gateway-cognito-m2m \\
    --env IDENTITY_AUTH_FLOW=M2M \\
    --env IDENTITY_SCOPES=lauki-demo-gateway/invoke \\
    --env TAVILY_API_KEY=...
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from _shared import (
    MEMORY_ID,
    MemoryMiddleware,
    build_memory,
    load_gateway_mcp_tools,
    memory_config,
)

load_dotenv()
app = BedrockAgentCoreApp()

PROVIDER = os.getenv("IDENTITY_PROVIDER_NAME", "gateway-cognito-m2m")
SCOPES = [
    s.strip()
    for s in os.getenv("IDENTITY_SCOPES", "lauki-demo-gateway/invoke").split(",")
    if s.strip()
]
AUTH_FLOW = os.getenv("IDENTITY_AUTH_FLOW", "M2M")  # type: ignore[assignment]


@tool
def web_search(query: str) -> str:
    """Search the public web. Use for current events and facts not in memory."""
    key = os.getenv("TAVILY_API_KEY")
    if key:
        try:
            from tavily import TavilyClient

            result = TavilyClient(api_key=key).search(query, max_results=3)
            lines = [
                f"- {hit.get('title')}: {hit.get('content', '')[:280]}"
                for hit in result.get("results", [])
            ]
            return "\n".join(lines) or "No web results."
        except Exception as exc:  # noqa: BLE001
            return f"Tavily failed ({exc}). Falling back."

    try:
        from ddgs import DDGS

        hits = list(DDGS().text(query, max_results=3))
        return "\n".join(
            f"- {h.get('title')}: {h.get('body', '')[:280]}" for h in hits
        ) or "No web results."
    except Exception as exc:  # noqa: BLE001
        return (
            f"Web search unavailable ({exc}). "
            "Set TAVILY_API_KEY or install ddgs / tavily-python."
        )


@tool
def get_current_datetime() -> str:
    """Return the current UTC date and time."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC (%A)")


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple math expression. Example: '12 * 3.5 + 10'."""
    allowed = set("0123456789+-*/().% ")
    if not expression or any(ch not in allowed for ch in expression):
        return "Only numbers and + - * / ( ) . % are allowed."
    try:
        value = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:  # noqa: BLE001
        return f"Could not evaluate `{expression}`: {exc}"
    return f"{expression} = {value}"


def _load_rag_chunks() -> list[tuple[str, str]]:
    """Load FAQ + markdown docs as (source, text) chunks for keyword RAG."""
    chunks: list[tuple[str, str]] = []
    # FAQ CSV (same corpus as other demos)
    try:
        from _shared import FAQ_DOCS

        for i, doc in enumerate(FAQ_DOCS):
            chunks.append((f"faq:{i}", doc.page_content))
    except Exception as exc:  # noqa: BLE001
        print(f"FAQ load skipped: {exc}")

    docs_dirs = [
        os.path.join(os.path.dirname(__file__), "docs"),
        os.path.join(os.path.dirname(__file__), "rag_data"),
    ]
    seen: set[str] = set()
    for docs_dir in docs_dirs:
        if not os.path.isdir(docs_dir):
            continue
        for name in sorted(os.listdir(docs_dir)):
            if not name.endswith((".md", ".txt")):
                continue
            # Prefer first copy of the same filename
            if name in seen:
                continue
            seen.add(name)
            path = os.path.join(docs_dir, name)
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            # Split on ## headings for coarse chunks
            parts = re.split(r"\n(?=## )", text)
            for j, part in enumerate(parts):
                part = part.strip()
                if len(part) > 40:
                    chunks.append((f"{name}#{j}", part))
    return chunks


_RAG_CHUNKS = _load_rag_chunks()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


_STACK_TERMS = {
    "agentcore",
    "runtime",
    "memory",
    "gateway",
    "mcp",
    "identity",
    "oauth",
    "cognito",
    "rag",
    "harness",
    "langgraph",
}


@tool
def search_docs(query: str, k: int = 4) -> str:
    """RAG over AgentCore docs + Lauki FAQ. Use for Runtime/Memory/Gateway/MCP/Identity
    questions or Lauki phone product FAQs.

    Args:
        query: Natural language question or keywords.
        k: Max chunks to return (default 4).
    """
    q = _tokenize(query)
    if not _RAG_CHUNKS:
        return "Knowledge base is empty."
    if not q:
        picked = _RAG_CHUNKS[:k]
    else:
        scored: list[tuple[float, str, str]] = []
        q_lower = query.lower()
        wants_stack = bool(q & _STACK_TERMS)
        for source, text in _RAG_CHUNKS:
            tokens = _tokenize(text)
            overlap = q & tokens
            score = float(len(overlap))
            if not score:
                continue
            # Prefer knowledge-base markdown for stack/platform questions
            if wants_stack and (source.endswith(".md") or ".md#" in source or source.startswith("agentcore")):
                score += 4.0 + 2.0 * len(overlap & _STACK_TERMS)
            # Soft-penalize FAQ when the question is clearly about AgentCore
            if wants_stack and source.startswith("faq:"):
                score *= 0.35
            if q_lower in text.lower():
                score += 5.0
            scored.append((score, source, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [(s, t) for _, s, t in scored[:k]] or _RAG_CHUNKS[:k]
    blocks = []
    for i, (source, text) in enumerate(picked, 1):
        blocks.append(f"[{i}] source={source}\n{text[:900]}")
    return (
        f"Retrieved {len(picked)} chunks for query={query!r}:\n\n"
        + "\n\n---\n\n".join(blocks)
    )


LOCAL_TOOLS = [web_search, get_current_datetime, calculator, search_docs]

TOOL_LABELS = {
    "web_search": "Searching the web",
    "get_current_datetime": "Looking up current date/time",
    "calculator": "Running calculator",
    "search_docs": "RAG over docs + FAQ",
    "get_weather": "Checking weather via Gateway MCP",
    "get_time": "Checking time via Gateway MCP",
}


def _friendly_tool_label(name: str) -> str:
    if name in TOOL_LABELS:
        return TOOL_LABELS[name]
    short = name.split("___")[-1] if "___" in name else name
    if short in TOOL_LABELS:
        return TOOL_LABELS[short]
    if "weather" in short.lower():
        return "Checking weather via Gateway MCP"
    if "time" in short.lower() and "date" not in short.lower():
        return "Checking time via Gateway MCP"
    if "search_docs" in short.lower() or "docs" in short.lower():
        return "RAG over docs + FAQ"
    return f"Calling {short}"


@requires_access_token(
    provider_name=PROVIDER,
    scopes=SCOPES,
    auth_flow=AUTH_FLOW,  # type: ignore[arg-type]
    into="access_token",
)
def fetch_identity_token(*, access_token: str) -> str:
    """OAuth access token via AgentCore Identity (injected by decorator)."""
    return access_token


def resolve_gateway_token() -> tuple[str, str, str]:
    """Return (token, auth_source, error). Prefer Identity; fall back to GATEWAY_TOKEN.

    Identity needs a Workload Access Token. With SIGV4 invokes, pass
    ``runtimeUserId`` so the Runtime mints a WAT into context.
    """
    static = os.getenv("GATEWAY_TOKEN", "").strip()
    err = ""
    try:
        token = fetch_identity_token()
        if token:
            return token, "identity", ""
        err = "Identity returned empty token"
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
        print(f"Identity token fetch failed: {err}")

    if static:
        return static, "gateway_token", err
    return "", "none", err


def build_tools(*, allow_identity: bool = True) -> tuple[list, dict]:
    """Local tools + optional Gateway MCP tools. Returns (tools, stack_meta)."""
    tools = list(LOCAL_TOOLS)
    meta = {
        "runtime": True,
        "memory": True,
        "gateway": False,
        "mcp": False,
        "identity": False,
        "rag": True,
        "identity_provider": PROVIDER,
        "memory_id": MEMORY_ID,
        "gateway_url": os.getenv("GATEWAY_URL", "").strip()[:120],
        "gateway_tools": [],
        "auth_source": "none",
        "identity_error": "",
        "rag_chunks": len(_RAG_CHUNKS),
    }
    gateway_url = os.getenv("GATEWAY_URL", "").strip()
    if not gateway_url:
        print("GATEWAY_URL not set — local research tools only")
        return tools, meta

    if allow_identity:
        token, auth_source, id_err = resolve_gateway_token()
    else:
        token = os.getenv("GATEWAY_TOKEN", "").strip()
        auth_source = "gateway_token" if token else "none"
        id_err = "deferred until invoke (needs Runtime WAT)"

    meta["auth_source"] = auth_source
    meta["identity"] = auth_source == "identity"
    meta["identity_error"] = id_err

    if not token:
        print("No Identity/GATEWAY_TOKEN — skipping Gateway MCP")
        return tools, meta

    try:
        mcp_tools = load_gateway_mcp_tools(gateway_url, token)
        # Drop Gateway's built-in search — it often loops with the local web_search tool
        mcp_tools = [
            t
            for t in mcp_tools
            if "x_amz_bedrock_agentcore_search" not in getattr(t, "name", "")
        ]
        tools.extend(mcp_tools)
        meta["gateway"] = True
        meta["mcp"] = bool(mcp_tools)
        meta["gateway_tools"] = [getattr(t, "name", str(t)) for t in mcp_tools]
        print(
            f"Loaded {len(mcp_tools)} Gateway MCP tools "
            f"(auth={auth_source}, provider={PROVIDER})"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Gateway MCP load failed: {exc}")
    return tools, meta


def extract_agent_steps(messages: list) -> list[dict]:
    """Turn LangGraph message history into UI-friendly step records."""
    steps: list[dict] = []
    n = 0
    for msg in messages:
        msg_type = getattr(msg, "type", "") or ""
        tool_calls = getattr(msg, "tool_calls", None) or []

        for tc in tool_calls:
            n += 1
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            steps.append(
                {
                    "index": n,
                    "kind": "tool_call",
                    "tool": name,
                    "label": _friendly_tool_label(name),
                    "input": args,
                    "status": "called",
                }
            )

        if msg_type == "tool":
            n += 1
            name = getattr(msg, "name", None) or "tool"
            content = getattr(msg, "content", "")
            if not isinstance(content, str):
                content = str(content)
            steps.append(
                {
                    "index": n,
                    "kind": "tool_result",
                    "tool": name,
                    "label": f"Got result from {name.split('___')[-1]}",
                    "output": content[:1200],
                    "status": "ok",
                }
            )
            continue

        if msg_type == "ai" and not tool_calls:
            content = getattr(msg, "content", "") or ""
            if isinstance(content, list):
                content = "\n".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("text")
                )
            if str(content).strip():
                n += 1
                steps.append(
                    {
                        "index": n,
                        "kind": "assistant",
                        "label": "Composing answer",
                        "output": str(content)[:2000],
                        "status": "done",
                    }
                )
    return steps


def extract_token_usage(messages: list) -> dict:
    """Sum OpenAI / LangChain token usage across AI messages."""
    prompt_tokens = 0
    completion_tokens = 0
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    for msg in messages:
        md = getattr(msg, "response_metadata", None) or {}
        if md.get("model_name"):
            model = md["model_name"]
        tu = md.get("token_usage") or md.get("usage") or {}
        prompt_tokens += int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
        completion_tokens += int(
            tu.get("completion_tokens") or tu.get("output_tokens") or 0
        )
        um = getattr(msg, "usage_metadata", None) or {}
        if um:
            prompt_tokens += int(um.get("input_tokens") or 0)
            completion_tokens += int(um.get("output_tokens") or 0)
    total = prompt_tokens + completion_tokens
    # gpt-4o-mini list prices (USD per 1M tokens) — update if you change models
    rates = {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (2.50, 10.00),
        "gpt-4.1-mini": (0.40, 1.60),
    }
    key = next((k for k in rates if k in (model or "")), "gpt-4o-mini")
    in_rate, out_rate = rates[key]
    cost_usd = (prompt_tokens / 1_000_000) * in_rate + (
        completion_tokens / 1_000_000
    ) * out_rate
    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "input_rate_per_m": in_rate,
        "output_rate_per_m": out_rate,
        "estimated_cost_usd": round(cost_usd, 6),
    }


def _tools_available_list(stack: dict) -> list[dict]:
    tools_available = [
        {"name": "web_search", "label": TOOL_LABELS["web_search"], "source": "local"},
        {
            "name": "get_current_datetime",
            "label": TOOL_LABELS["get_current_datetime"],
            "source": "local",
        },
        {"name": "calculator", "label": TOOL_LABELS["calculator"], "source": "local"},
        {"name": "search_docs", "label": TOOL_LABELS["search_docs"], "source": "rag"},
    ]
    for name in stack.get("gateway_tools") or []:
        tools_available.append(
            {
                "name": name,
                "label": _friendly_tool_label(name),
                "source": "gateway_mcp",
            }
        )
    return tools_available


def _step_from_stream_messages(messages: list, *, seen: set) -> list[dict]:
    """Emit only newly observed tool/assistant steps from a stream update."""
    fresh: list[dict] = []
    for step in extract_agent_steps(messages):
        key = (
            step.get("kind"),
            step.get("tool"),
            str(step.get("input") or step.get("output") or "")[:80],
            step.get("index"),
        )
        if key in seen:
            continue
        seen.add(key)
        fresh.append(step)
    return fresh


SYSTEM_PROMPT = """You are a helpful research assistant with local tools, RAG docs, and optional Gateway MCP tools.

When to use tools (only if needed):
1. AgentCore / Lauki FAQ knowledge → search_docs (RAG).
2. Public facts / news → web_search.
3. Current UTC date/time → get_current_datetime.
4. Arithmetic → calculator (do not guess).
5. Weather or city local time → Gateway MCP get_weather / get_time when available.

When NOT to use tools:
- Personal questions (name, identity, preferences) unless prior chat memory clearly has the answer.
- Simple greetings or chit-chat.
- Anything you can answer from the conversation itself.

Rules:
- Prefer zero tools when a direct answer is enough.
- Never invent tool results. If a tool fails, say so.
- Keep answers concise unless the user asks for detail.
"""

model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)

checkpointer, store = build_memory()
# Cold start: avoid Identity (needs Runtime WAT). GATEWAY_TOKEN can still preload MCP.
_tools, _stack = build_tools(allow_identity=False)

agent = create_agent(
    model=model,
    tools=_tools,
    checkpointer=checkpointer,
    store=store,
    middleware=[MemoryMiddleware()],
    system_prompt=SYSTEM_PROMPT,
    name="research_agent",
)


@app.entrypoint
def agent_invocation(payload, context):
    """SSE stream: progress → tool steps → final answer with tokens/cost.

    Yielding dicts makes InvokeAgentRuntime return text/event-stream so the UI
    can show intermediate AgentCore / LangGraph activity live.
    """
    import time as _time

    t0 = _time.time()
    print("Received payload:", payload)
    print("MEMORY_ID:", MEMORY_ID)
    print("GATEWAY_URL set:", bool(os.getenv("GATEWAY_URL")))
    print("IDENTITY_PROVIDER_NAME:", PROVIDER)

    yield {
        "event": "progress",
        "phase": "start",
        "message": "Runtime accepted invoke · resolving Identity + Gateway MCP",
        "elapsed_s": 0.0,
    }

    global agent
    tools, stack = build_tools(allow_identity=True)
    agent = create_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        store=store,
        middleware=[MemoryMiddleware()],
        system_prompt=SYSTEM_PROMPT,
        name="research_agent",
    )

    yield {
        "event": "progress",
        "phase": "stack_ready",
        "message": (
            f"Stack ready · auth={stack.get('auth_source')} · "
            f"mcp_tools={len(stack.get('gateway_tools') or [])} · "
            f"rag_chunks={stack.get('rag_chunks')}"
        ),
        "stack": stack,
        "elapsed_s": round(_time.time() - t0, 3),
    }

    query = payload.get("prompt", "No prompt found in input")
    cfg = memory_config(payload, context)
    run_cfg = {"configurable": cfg["configurable"], "recursion_limit": 40}
    seen: set = set()
    final_messages: list = []

    try:
        yield {
            "event": "progress",
            "phase": "agent_run",
            "message": "LangGraph agent running (stream_mode=values+messages)",
            "elapsed_s": round(_time.time() - t0, 3),
        }
        answer_parts: list[str] = []
        for mode, chunk in agent.stream(
            {"messages": [("human", query)]},
            config=run_cfg,
            stream_mode=["values", "messages"],
        ):
            if mode == "values":
                messages = (chunk or {}).get("messages") or []
                final_messages = messages
                for step in _step_from_stream_messages(messages, seen=seen):
                    yield {
                        "event": "step",
                        "step": step,
                        "elapsed_s": round(_time.time() - t0, 3),
                    }
                continue

            if mode != "messages":
                continue

            # Token / chunk stream from the model (and tool messages)
            msg = chunk[0] if isinstance(chunk, tuple) else chunk
            meta = chunk[1] if isinstance(chunk, tuple) and len(chunk) > 1 else {}
            msg_type = getattr(msg, "type", "") or ""
            node = (meta or {}).get("langgraph_node") if isinstance(meta, dict) else None

            # Stream assistant answer tokens only (not tool payloads)
            if msg_type not in ("AIMessageChunk", "ai"):
                continue
            if node not in (None, "model", "agent"):
                continue

            delta = getattr(msg, "content", "") or ""
            if isinstance(delta, list):
                delta = "".join(
                    b.get("text", "")
                    for b in delta
                    if isinstance(b, dict) and b.get("text")
                )
            delta = str(delta)
            if not delta:
                continue

            answer_parts.append(delta)
            yield {
                "event": "token",
                "delta": delta,
                "elapsed_s": round(_time.time() - t0, 3),
            }
    except Exception as exc:  # noqa: BLE001
        print(f"agent.stream failed: {type(exc).__name__}: {exc}")
        yield {
            "event": "final",
            "result": f"Agent error: {exc}",
            "steps": [],
            "tools_available": _tools_available_list(stack),
            "stack": stack,
            "usage": extract_token_usage([]),
            "metrics": {
                "elapsed_s": round(_time.time() - t0, 3),
                "estimated_cost_usd": 0.0,
            },
            "actor_id": cfg["actor_id"],
            "thread_id": cfg["thread_id"],
            "memory_id": MEMORY_ID,
            "identity_provider": PROVIDER if stack.get("identity") else None,
            "demo": "research+memory+gateway+identity+stream",
            "error": f"{type(exc).__name__}: {exc}",
        }
        return

    messages = final_messages
    final = "".join(answer_parts) if answer_parts else (
        messages[-1].content if messages else ""
    )
    if isinstance(final, list):
        final = "\n".join(
            b.get("text", "") for b in final if isinstance(b, dict) and b.get("text")
        )
    # Prefer full last AI message if richer than streamed join
    if messages:
        last_content = messages[-1].content
        if isinstance(last_content, list):
            last_content = "\n".join(
                b.get("text", "")
                for b in last_content
                if isinstance(b, dict) and b.get("text")
            )
        if last_content and len(str(last_content)) >= len(str(final)):
            final = last_content
    steps = extract_agent_steps(messages)
    usage = extract_token_usage(messages)
    elapsed = round(_time.time() - t0, 3)

    yield {
        "event": "final",
        "result": final,
        "steps": steps,
        "tools_available": _tools_available_list(stack),
        "stack": stack,
        "usage": usage,
        "metrics": {
            "elapsed_s": elapsed,
            "estimated_cost_usd": usage.get("estimated_cost_usd", 0.0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "model": usage.get("model"),
        },
        "actor_id": cfg["actor_id"],
        "thread_id": cfg["thread_id"],
        "memory_id": MEMORY_ID,
        "identity_provider": PROVIDER if stack.get("identity") else None,
        "demo": "research+memory+gateway+identity+stream",
    }


if __name__ == "__main__":
    app.run()
