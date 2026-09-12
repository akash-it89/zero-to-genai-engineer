"""Shared helpers for AgentCore demo runtimes (FAQ tools, model, memory)."""

from __future__ import annotations

import csv
import os
import re
import uuid
from typing import Any, List

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_aws import ChatBedrockConverse
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool, tool
from langchain_openai import ChatOpenAI
from langgraph.store.base import BaseStore
from langgraph_checkpoint_aws import AgentCoreMemorySaver, AgentCoreMemoryStore

REGION = os.getenv("AWS_REGION") or "us-west-2"
# Empty MEMORY_ID="" from --env must NOT wipe the default (getenv returns "" not None)
MEMORY_ID = (os.getenv("MEMORY_ID") or "memorybot-w6GzC7D97L").strip()


def load_faq_csv(path: str = "./lauki_qna.csv") -> List[Document]:
    docs: List[Document] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row["question"].strip()
            a = row["answer"].strip()
            docs.append(Document(page_content=f"Q: {q}\nA: {a}"))
    return docs


FAQ_DOCS = load_faq_csv()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def keyword_search(query: str, k: int = 3) -> List[Document]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return FAQ_DOCS[:k]
    scored: list[tuple[int, Document]] = []
    for doc in FAQ_DOCS:
        score = len(q_tokens & _tokenize(doc.page_content))
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:k]]


def _format_results(results: List[Document], label: str = "FAQ Entry") -> str:
    if not results:
        return "No relevant FAQ entries found."
    context = "\n\n---\n\n".join(
        f"{label} {i + 1}:\n{doc.page_content}" for i, doc in enumerate(results)
    )
    return f"Found {len(results)} relevant FAQ entries:\n\n{context}"


@tool
def search_faq(query: str) -> str:
    """Search the local FAQ knowledge base (Lauki phones)."""
    return _format_results(keyword_search(query, k=3))


@tool
def search_detailed_faq(query: str, num_results: int = 5) -> str:
    """Search the FAQ with more results for complex queries."""
    return _format_results(keyword_search(query, k=num_results))


@tool
def reformulate_query(original_query: str, focus_aspect: str) -> str:
    """Search FAQ with a reformulated focus aspect."""
    results = keyword_search(f"{focus_aspect} {original_query}", k=3)
    if not results:
        return f"No results found for aspect: {focus_aspect}"
    return _format_results(results, label="Entry")


FAQ_TOOLS = [search_faq, search_detailed_faq, reformulate_query]


class MemoryMiddleware(AgentMiddleware):
    """Persist turns to AgentCore Memory and optionally recall preferences."""

    def pre_model_hook(self, state: AgentState, config: RunnableConfig, *, store: BaseStore):
        actor_id = config["configurable"]["actor_id"]
        thread_id = config["configurable"]["thread_id"]
        namespace = (actor_id, thread_id)
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                store.put(namespace, str(uuid.uuid4()), {"message": msg})
                try:
                    prefs = store.search(("preferences", actor_id), query=msg.content, limit=5)
                    if prefs:
                        print("Retrieved memories:", prefs)
                except Exception as exc:  # noqa: BLE001
                    print(f"Memory retrieval error: {exc}")
                break
        return {"messages": messages}

    def post_model_hook(self, state, config: RunnableConfig, *, store: BaseStore):
        actor_id = config["configurable"]["actor_id"]
        thread_id = config["configurable"]["thread_id"]
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                store.put((actor_id, thread_id), str(uuid.uuid4()), {"message": msg})
                break
        return state


def build_memory():
    if len(MEMORY_ID) < 12:
        raise RuntimeError(
            "MEMORY_ID is missing/too short. Pass it at launch, e.g.\n"
            "  agentcore launch -a <agent> --env MEMORY_ID=memorybot-w6GzC7D97L\n"
            f"Current MEMORY_ID={MEMORY_ID!r} REGION={REGION!r}"
        )
    print(f"AgentCore Memory: MEMORY_ID={MEMORY_ID} REGION={REGION}")
    checkpointer = AgentCoreMemorySaver(memory_id=MEMORY_ID, region_name=REGION)
    store = AgentCoreMemoryStore(memory_id=MEMORY_ID, region_name=REGION)
    return checkpointer, store


def build_model():
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("Using ChatOpenAI")
        return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=openai_key)
    print("Using ChatBedrockConverse")
    return ChatBedrockConverse(
        model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"),
        region_name=REGION,
        temperature=0,
    )


def memory_config(payload: dict, context: Any) -> dict:
    actor_id = payload.get("actor_id", "default-user")
    thread_id = payload.get(
        "thread_id",
        payload.get("session_id", getattr(context, "session_id", None) or "default-session"),
    )
    return {
        "configurable": {"actor_id": actor_id, "thread_id": thread_id},
        "actor_id": actor_id,
        "thread_id": thread_id,
    }


def _json_schema_to_args_model(tool_name: str, input_schema: dict | None):
    """Build a Pydantic args model from an MCP JSON Schema so the LLM gets real params."""
    from pydantic import Field, create_model

    props = (input_schema or {}).get("properties") or {}
    required = set((input_schema or {}).get("required") or [])
    fields: dict = {}
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, spec in props.items():
        py_type = type_map.get((spec or {}).get("type", "string"), str)
        desc = (spec or {}).get("description") or key
        if key in required:
            fields[key] = (py_type, Field(..., description=desc))
        else:
            fields[key] = (py_type | None, Field(default=None, description=desc))
    if not fields:
        # MCP tool with no args — keep a harmless optional placeholder
        fields["_unused"] = (str | None, Field(default=None, description="unused"))
    safe = "".join(ch if ch.isalnum() else "_" for ch in tool_name)[:40]
    return create_model(f"{safe}_Args", **fields)


def _unwrap_mcp_content(result: dict) -> str:
    """Flatten MCP tool result text (handles nested Lambda statusCode/body JSON)."""
    import json as _json

    content = result.get("content") or result
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            else:
                texts.append(str(item))
        raw = "\n".join(texts)
    else:
        raw = str(content)

    # Demo Lambda returns {"statusCode":200,"body":"{...}"} — unwrap for the LLM
    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, dict) and "body" in parsed:
            body = parsed["body"]
            if isinstance(body, str):
                try:
                    body = _json.loads(body)
                except Exception:  # noqa: BLE001
                    pass
            return _json.dumps(body, ensure_ascii=False)
        return _json.dumps(parsed, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return raw


def load_gateway_mcp_tools(gateway_url: str, access_token: str) -> list:
    """Turn AgentCore Gateway MCP tools into LangChain StructuredTools (JSON-RPC)."""
    import httpx

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
        body = list_resp.json()
        tools_meta = body.get("result", {}).get("tools", [])
        print(f"Gateway MCP tools discovered: {[t.get('name') for t in tools_meta]}")

        lc_tools = []
        for meta in tools_meta:
            mcp_name = meta["name"]
            description = meta.get("description") or f"MCP tool {mcp_name}"
            args_model = _json_schema_to_args_model(mcp_name, meta.get("inputSchema"))

            def _make_runner(tool_name: str):
                def _run(**kwargs) -> str:
                    # Drop placeholder / nulls
                    args = {k: v for k, v in kwargs.items() if v is not None and k != "_unused"}
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
                        if result.get("isError"):
                            return f"Tool error: {_unwrap_mcp_content(result)}"
                        return _unwrap_mcp_content(result)

                return _run

            lc_name = mcp_name.replace("-", "_")[:64]
            lc_tools.append(
                StructuredTool.from_function(
                    func=_make_runner(mcp_name),
                    name=lc_name,
                    description=description,
                    args_schema=args_model,
                )
            )
        return lc_tools
