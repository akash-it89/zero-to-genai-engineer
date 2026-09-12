"""
AgentCore Runtime: EXPLICIT LangGraph StateGraph research agent.

Graph (nodes + edges you can see):

    START → agent ──tools_condition──► tools → agent → … → END
              │
              └─ (no tool calls) ──────────────────────────► END

Same stack as the create_agent demo:
  Memory (checkpointer + store) · Gateway MCP · Identity · RAG · local tools · AgentCore Browser

Preserved create_agent copy:
  research_create_agent_agentcore.py
  (and langgraph_research_agentcore.py — still the deployed create_agent Runtime)

Configure & launch THIS graph agent as a separate Runtime:
  agentcore configure -e langgraph_research_graph_agentcore.py -n langgraph_research_graph
  agentcore launch -a langgraph_research_graph \\
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
import time as _time
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.base import BaseStore

from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Reuse tools / Identity / RAG / step+usage helpers from the preserved create_agent copy
from research_create_agent_agentcore import (
    MEMORY_ID,
    PROVIDER,
    SYSTEM_PROMPT,
    _tools_available_list,
    build_tools,
    extract_agent_steps,
    extract_token_usage,
    model,
)
from _shared import build_memory, memory_config

load_dotenv()
app = BedrockAgentCoreApp()

checkpointer, store = build_memory()


def build_research_graph(tools: list):
    """Compile an explicit ReAct-style StateGraph: agent ↔ ToolNode."""
    llm = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(
        state: MessagesState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> dict[str, Any]:
        """LLM node — may emit tool_calls or a final text answer."""
        cfg = config.get("configurable") or {}
        actor_id = cfg.get("actor_id", "default-user")
        thread_id = cfg.get("thread_id", "default-session")
        namespace = (actor_id, thread_id)

        messages = list(state.get("messages") or [])
        # Persist latest human turn into AgentCore Memory store (same idea as MemoryMiddleware)
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                try:
                    store.put(namespace, str(uuid.uuid4()), {"message": msg})
                except Exception as exc:  # noqa: BLE001
                    print(f"store.put(human) failed: {exc}")
                break

        # System prompt once at the front of the model call (not duplicated in state)
        model_input = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        response = llm.invoke(model_input, config=config)

        if isinstance(response, AIMessage):
            try:
                store.put(namespace, str(uuid.uuid4()), {"message": response})
            except Exception as exc:  # noqa: BLE001
                print(f"store.put(ai) failed: {exc}")

        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    # tools_condition: if last AIMessage has tool_calls → "tools", else END
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer, store=store)


# Cold start without Identity WAT (same pattern as create_agent entrypoint)
_tools, _stack = build_tools(allow_identity=False)
graph_app = build_research_graph(_tools)


def _step_from_stream_messages(messages: list, *, seen: set) -> list[dict]:
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


@app.entrypoint
def agent_invocation(payload, context):
    """SSE stream from an explicit LangGraph StateGraph (nodes: agent, tools)."""
    t0 = _time.time()
    print("Received payload:", payload)
    print("GRAPH: START→agent⇄tools→END  (explicit StateGraph)")
    print("MEMORY_ID:", MEMORY_ID)
    print("GATEWAY_URL set:", bool(os.getenv("GATEWAY_URL")))
    print("IDENTITY_PROVIDER_NAME:", PROVIDER)

    yield {
        "event": "progress",
        "phase": "start",
        "message": "Runtime accepted invoke · StateGraph · resolving Identity + Gateway MCP",
        "elapsed_s": 0.0,
        "graph": {"nodes": ["agent", "tools"], "edges": ["START→agent", "agent⇄tools", "agent→END"]},
    }

    global graph_app
    tools, stack = build_tools(allow_identity=True)
    graph_app = build_research_graph(tools)

    yield {
        "event": "progress",
        "phase": "stack_ready",
        "message": (
            f"StateGraph ready · auth={stack.get('auth_source')} · "
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
    answer_parts: list[str] = []

    try:
        yield {
            "event": "progress",
            "phase": "agent_run",
            "message": "StateGraph streaming (stream_mode=values+messages)",
            "elapsed_s": round(_time.time() - t0, 3),
        }
        for mode, chunk in graph_app.stream(
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

            msg = chunk[0] if isinstance(chunk, tuple) else chunk
            meta = chunk[1] if isinstance(chunk, tuple) and len(chunk) > 1 else {}
            msg_type = getattr(msg, "type", "") or ""
            node = (meta or {}).get("langgraph_node") if isinstance(meta, dict) else None

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
        print(f"graph.stream failed: {type(exc).__name__}: {exc}")
        yield {
            "event": "final",
            "result": f"Agent error: {exc}",
            "steps": [],
            "tools_available": _tools_available_list(stack),
            "stack": stack,
            "usage": extract_token_usage([]),
            "metrics": {"elapsed_s": round(_time.time() - t0, 3), "estimated_cost_usd": 0.0},
            "actor_id": cfg["actor_id"],
            "thread_id": cfg["thread_id"],
            "memory_id": MEMORY_ID,
            "identity_provider": PROVIDER if stack.get("identity") else None,
            "demo": "langgraph-stategraph+memory+gateway+identity",
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
        "demo": "langgraph-stategraph+memory+gateway+identity",
        "graph": {
            "framework": "langgraph.StateGraph",
            "nodes": ["agent", "tools"],
            "pattern": "ReAct (explicit edges via tools_condition)",
        },
    }


if __name__ == "__main__":
    app.run()
