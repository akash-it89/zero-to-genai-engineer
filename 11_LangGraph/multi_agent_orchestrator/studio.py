"""LangGraph Studio entry point.

    cd 11_LangGraph/multi_agent_orchestrator
    python3 -m langgraph dev

Studio loads `graph` from this file. MCP + RAG stay in graph.py — we do not
rebuild the helpdesk, we only compile the same orchestrator without our own
checkpointer so the IDE can persist threads and HITL pauses.
"""

from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parents[1] / "10_RAG" / ".env", override=False)
load_dotenv(HERE.parents[2] / ".env", override=False)

from graph import build_orchestrator, enable_langsmith  # noqa: E402

enable_langsmith()
_bundle = build_orchestrator(user_id="studio-user", for_studio=True)
graph = _bundle["graph"]
