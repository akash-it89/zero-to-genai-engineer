"""Shared helpers for Strands + AgentCore demos (FAQ tools, model, Memory, Gateway)."""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from strands import tool
from strands.models import BedrockModel
from strands.models.openai import OpenAIModel

load_dotenv()

REGION = (os.getenv("AWS_REGION") or "us-east-1").strip()
MEMORY_ID = (os.getenv("MEMORY_ID") or "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

SUPPORT_SYSTEM_PROMPT = """You are Lauki Support Copilot — a helpful product support agent.

Guidelines:
1. Prefer search_faq for activation, eSIM, plans, roaming, and troubleshooting questions.
2. Use get_current_datetime for time-sensitive answers.
3. Use web_search only when the FAQ does not cover the question.
4. If Gateway tools (weather/time) are available, use them when relevant.
5. Be concise, accurate, and say clearly when you do not know.
"""


def load_faq_rows(path: str = "./lauki_qna.csv") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "question": row["question"].strip(),
                    "answer": row["answer"].strip(),
                }
            )
    return rows


FAQ_ROWS = load_faq_rows()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def keyword_search(query: str, k: int = 3) -> list[dict[str, str]]:
    """Token-overlap FAQ retrieval — no embeddings, no quota burn."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return FAQ_ROWS[:k]
    scored: list[tuple[int, dict[str, str]]] = []
    for row in FAQ_ROWS:
        blob = f"{row['question']} {row['answer']}"
        score = len(q_tokens & _tokenize(blob))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:k]]


def _format_faq(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No relevant FAQ entries found."
    parts = [
        f"FAQ {i + 1}:\nQ: {r['question']}\nA: {r['answer']}" for i, r in enumerate(rows)
    ]
    return "Found relevant FAQ entries:\n\n" + "\n\n---\n\n".join(parts)


@tool
def search_faq(query: str) -> str:
    """Search the Lauki FAQ knowledge base for product and support answers."""
    return _format_faq(keyword_search(query, k=3))


@tool
def search_detailed_faq(query: str, num_results: int = 5) -> str:
    """Search the FAQ with more results for complex support questions."""
    return _format_faq(keyword_search(query, k=num_results))


@tool
def get_current_datetime() -> str:
    """Return the current UTC date and time."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"Current datetime: {now}"


@tool
def web_search(query: str) -> str:
    """Search the web for current information when the FAQ is not enough."""
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    if tavily_key:
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=tavily_key)
            resp = client.search(query, max_results=3)
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

        results = DDGS().text(query, max_results=3)
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


FAQ_TOOLS = [search_faq, search_detailed_faq, get_current_datetime]
SUPPORT_TOOLS = FAQ_TOOLS + [web_search]


def apply_bedrock_guardrail(text: str, *, source: str = "INPUT") -> tuple[str, bool]:
    """
    Run Amazon Bedrock Guardrails ApplyGuardrail on text.

    Works with OpenAI or Bedrock LLMs (does not require Converse guardrailConfig).
    Returns (possibly_replaced_text, intervened).
    """
    guardrail_id = os.getenv("GUARDRAIL_ID", "").strip()
    if not guardrail_id or not (text or "").strip():
        return text, False

    version = (os.getenv("GUARDRAIL_VERSION") or "DRAFT").strip()
    import boto3

    client = boto3.client("bedrock-runtime", region_name=REGION)
    resp = client.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=version,
        source=source,  # INPUT | OUTPUT
        content=[{"text": {"text": text}}],
    )
    action = (resp.get("action") or "").upper()
    if action != "GUARDRAIL_INTERVENED":
        return text, False

    outputs = resp.get("outputs") or []
    if outputs and isinstance(outputs[0], dict):
        replaced = (outputs[0].get("text") or "").strip()
        if replaced:
            return replaced, True
    fallback = (
        "I can't help with that request. Please ask about Lauki plans, "
        "activation, eSIM, or other product support."
        if source == "INPUT"
        else "I can't share that content. Please ask a Lauki support question."
    )
    return fallback, True


def build_model():
    """
    Model selection:
      - USE_BEDROCK=true  → BedrockModel (+ optional Converse Guardrail config)
      - else if OPENAI_API_KEY → OpenAIModel (classroom default; pair with ApplyGuardrail)
      - else → BedrockModel
    """
    use_bedrock = os.getenv("USE_BEDROCK", "").strip().lower() in {"1", "true", "yes"}
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    guardrail_id = os.getenv("GUARDRAIL_ID", "").strip()
    guardrail_version = (os.getenv("GUARDRAIL_VERSION") or "1").strip()

    if use_bedrock or not openai_key:
        kwargs: dict[str, Any] = {
            "model_id": BEDROCK_MODEL_ID,
            "region_name": REGION,
            "temperature": 0,
        }
        if guardrail_id:
            # Native Strands ↔ Bedrock Guardrails (requires Bedrock model access)
            kwargs.update(
                {
                    "guardrail_id": guardrail_id,
                    "guardrail_version": guardrail_version,
                    "guardrail_trace": "enabled",
                    "guardrail_redact_input": True,
                    "guardrail_redact_output": True,
                    "guardrail_redact_input_message": (
                        "I can't help with that request. Ask about Lauki plans, "
                        "activation, eSIM, or product support."
                    ),
                    "guardrail_redact_output_message": (
                        "I can't share that content. Please ask a Lauki support question."
                    ),
                }
            )
            print(
                f"Using BedrockModel ({BEDROCK_MODEL_ID}) + Guardrail "
                f"{guardrail_id}:{guardrail_version} in {REGION}"
            )
        else:
            print(f"Using BedrockModel ({BEDROCK_MODEL_ID}) in {REGION}")
        return BedrockModel(**kwargs)

    print(f"Using OpenAIModel ({OPENAI_MODEL})")
    if guardrail_id:
        print(
            f"Guardrail {guardrail_id}:{guardrail_version} via ApplyGuardrail "
            "(OpenAI LLM path)"
        )
    return OpenAIModel(
        client_args={"api_key": openai_key},
        model_id=OPENAI_MODEL,
        params={"temperature": 0},
    )


def require_memory_id() -> str:
    if len(MEMORY_ID) < 12:
        raise RuntimeError(
            "MEMORY_ID is missing/too short. Pass it at launch, e.g.\n"
            "  agentcore deploy -a strands_agent_memory "
            "--env MEMORY_ID=<your-memory-id> --env AWS_REGION=us-east-1\n"
            f"Current MEMORY_ID={MEMORY_ID!r} REGION={REGION!r}"
        )
    return MEMORY_ID


def session_ids(payload: dict, context: Any) -> tuple[str, str]:
    """Map invoke payload → (actor_id, session_id) for AgentCore Memory."""
    actor_id = (payload.get("actor_id") or "default-user").strip()
    session_id = (
        payload.get("thread_id")
        or payload.get("session_id")
        or getattr(context, "session_id", None)
        or "default-session"
    )
    return actor_id, str(session_id).strip()


def strands_text(result: Any) -> str:
    """Flatten a Strands AgentResult into plain text for Runtime responses."""
    try:
        message = getattr(result, "message", None) or {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and first.get("text"):
                return str(first["text"])
        return str(result)
    except Exception:  # noqa: BLE001
        return str(result)


def build_memory_session_manager(actor_id: str, session_id: str):
    """Create Strands session manager backed by AgentCore Memory."""
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )

    mem_id = require_memory_id()
    print(
        f"AgentCore Memory: MEMORY_ID={mem_id} REGION={REGION} "
        f"actor={actor_id} session={session_id}"
    )
    config = AgentCoreMemoryConfig(
        memory_id=mem_id,
        session_id=session_id,
        actor_id=actor_id,
    )
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=REGION,
    )


def load_gateway_mcp_tools(gateway_url: str, access_token: str):
    """
    Connect to AgentCore Gateway over MCP and return (mcp_client, tools).

    Caller must keep mcp_client alive while the agent runs.
    """
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp import MCPClient

    url = gateway_url.rstrip("/")
    token = access_token.strip()

    def _transport():
        return streamablehttp_client(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )

    mcp_client = MCPClient(_transport)
    mcp_client.start()
    tools = mcp_client.list_tools_sync()
    print(f"Gateway MCP tools loaded: {len(tools)}")
    return mcp_client, tools


def fetch_identity_token() -> str:
    """Mint Gateway JWT via AgentCore Identity (@requires_access_token)."""
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
