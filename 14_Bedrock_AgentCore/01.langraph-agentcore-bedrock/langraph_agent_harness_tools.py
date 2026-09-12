"""
Demo: AgentCore Runtime using Harness-style built-in tools
(Code Interpreter + Browser) — same capabilities Harness exposes,
but orchestrated in your LangGraph code on Runtime.

Also wires Memory so multi-turn sessions persist.

Requires IAM permissions for:
  bedrock-agentcore:StartCodeInterpreterSession / Invoke...
  bedrock-agentcore:StartBrowserSession / ...

Configure & launch:
  agentcore configure -e langraph_agent_harness_tools.py -n langraph_agent_harness_tools
  agentcore launch --env OPENAI_API_KEY=... --env MEMORY_ID=memorybot-w6GzC7D97L

Note: True "Harness" (zero-code managed loop) is created in the AWS Console
or via AgentCore CLI `harness` commands. See also: invoke_harness_client.py
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.tools.browser_client import BrowserClient
from bedrock_agentcore.tools.code_interpreter_client import code_session
from _shared import (
    FAQ_TOOLS,
    MEMORY_ID,
    REGION,
    MemoryMiddleware,
    build_memory,
    build_model,
    memory_config,
)

load_dotenv()
app = BedrockAgentCoreApp()

checkpointer, store = build_memory()
model = build_model()


def _format_code_interpreter_result(result: dict) -> str:
    """Consume EventStream from invoke_code_interpreter and return stdout/stderr.

    execute_code() returns a boto3 dict with a non-JSON-serializable `stream`.
    Dumping it with json.dumps hides the real output from the LLM.
    """
    parts: list[str] = []
    stream = result.get("stream")
    if stream is not None:
        for event in stream:
            # Typical shape:
            # {'result': {'content': [...], 'structuredContent': {...}, 'isError': False}}
            payload = event.get("result") if isinstance(event, dict) else None
            if not isinstance(payload, dict):
                parts.append(str(event)[:800])
                continue
            structured = payload.get("structuredContent") or {}
            stdout = structured.get("stdout")
            stderr = structured.get("stderr")
            exit_code = structured.get("exitCode")
            if stdout not in (None, ""):
                parts.append(f"stdout:\n{stdout}")
            if stderr not in (None, ""):
                parts.append(f"stderr:\n{stderr}")
            if exit_code is not None:
                parts.append(f"exit_code: {exit_code}")
            # Fallback: plain text content blocks
            if not stdout and not stderr:
                for block in payload.get("content") or []:
                    if isinstance(block, dict) and block.get("text"):
                        parts.append(block["text"])
            if payload.get("isError"):
                parts.append("isError: true")
    if not parts:
        # Last resort — drop the stream key so json.dumps works
        safe = {k: v for k, v in result.items() if k != "stream"}
        return json.dumps(safe, default=str)[:4000]
    return "\n".join(parts)[:4000]


@tool
def run_python_code(code: str) -> str:
    """Execute Python in AgentCore Code Interpreter (Harness-style sandbox).

    Args:
        code: Python source to run (pandas/numpy available in the sandbox).
    """
    try:
        # 👇 Use the Runtime's region (same place Code Interpreter is authorized)
        with code_session(REGION) as client:
            result = client.execute_code(code=code, language="python")
        return _format_code_interpreter_result(result)
    except Exception as exc:  # noqa: BLE001
        return f"Code Interpreter error: {exc}"


@tool
def start_browser_session(purpose: str = "demo") -> str:
    """Start an AgentCore Browser sandbox session and return a live-view URL.

    Args:
        purpose: Short label for why the browser session is needed.
    """
    try:
        client = BrowserClient(REGION)
        session_id = client.start(name=f"harness-demo-{purpose}"[:64])
        live_url = client.generate_live_view_url(expires=300)
        # Keep session alive briefly for the caller to open live view
        return (
            f"Browser session started.\n"
            f"session_id={session_id}\n"
            f"live_view_url={live_url}\n"
            f"purpose={purpose}\n"
            "Open the live_view_url in a browser within 5 minutes."
        )
    except Exception as exc:  # noqa: BLE001
        return f"Browser tool error: {exc}"


tools = FAQ_TOOLS + [run_python_code, start_browser_session]

system_prompt = """You are a demo agent showcasing AgentCore Harness-style tools on Runtime.

Capabilities:
1. FAQ search (search_faq)
2. Code Interpreter (run_python_code) — use for math, data analysis, scripts
3. Browser sandbox (start_browser_session) — returns a live-view URL

When the user asks to run code, call run_python_code.
When they ask to browse/open a page sandbox, call start_browser_session.
Remember the user across turns via memory.
"""

agent = create_agent(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
    store=store,
    middleware=[MemoryMiddleware()],
    system_prompt=system_prompt,
)


@app.entrypoint
def agent_invocation(payload, context):
    print("Received payload:", payload)
    query = payload.get("prompt", "No prompt found in input")
    cfg = memory_config(payload, context)
    result = agent.invoke(
        {"messages": [("human", query)]},
        config={"configurable": cfg["configurable"]},
    )
    return {
        "result": result["messages"][-1].content,
        "actor_id": cfg["actor_id"],
        "thread_id": cfg["thread_id"],
        "memory_id": MEMORY_ID,
        "demo": "runtime+memory+harness-tools",
    }


if __name__ == "__main__":
    app.run()
