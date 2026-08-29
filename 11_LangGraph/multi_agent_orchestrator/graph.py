"""
Hierarchical helpdesk orchestrator — the graph Notebook 03 builds and the
Streamlit app imports. One implementation so the notebook and the product cannot drift.

Reuses Module 10's helpdesk MCP server (SQL + RAG) from
`10_RAG/notebooks/production_mcp_agents_rag_capstone/`. This file does not
reimplement retrieval, SQLite, or FastMCP. It orchestrates specialists.

    top_supervisor
      ├── knowledge_team  (rag_agent, search_agent)
      └── ops_team        (sql_agent, ticket_agent)   writes → HumanInTheLoopMiddleware
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt

# ── Paths -----------------------------------------------------------------

HERE = Path(__file__).resolve().parent


def find_helpdesk_dir(start: Path | None = None) -> Path:
    """Walk up until the Module 10 helpdesk capstone folder is found."""
    here = (start or Path.cwd()).resolve()
    for folder in [here, *here.parents, HERE, *HERE.parents]:
        candidate = folder / "10_RAG" / "notebooks" / "production_mcp_agents_rag_capstone"
        if (candidate / "mcp_server.py").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not find 10_RAG/notebooks/production_mcp_agents_rag_capstone/. "
        "Open this from the course repo."
    )


def ensure_helpdesk_db(helpdesk_dir: Path) -> Path:
    """Create helpdesk.db if missing (deterministic seed, random.seed(42))."""
    db = helpdesk_dir / "helpdesk.db"
    if not db.is_file():
        subprocess.run(
            [sys.executable, str(helpdesk_dir / "seed_data.py")],
            check=True,
            cwd=helpdesk_dir,
        )
    return db


# ── Async helper (Jupyter already has a loop; Streamlit does not) ----------

def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import nest_asyncio

    nest_asyncio.apply()
    return asyncio.get_event_loop().run_until_complete(coro)


# ── MCP -------------------------------------------------------------------

READ_TOOLS = {
    "get_customer",
    "search_customers",
    "list_agents",
    "get_ticket",
    "list_tickets_by_customer",
    "list_tickets_by_agent",
    "get_ticket_notes",
    "get_customer_support_history",
    "get_agent_workload",
}

WRITE_TOOLS = {
    "create_customer",
    "update_customer",
    "create_ticket",
    "update_ticket_status",
    "update_ticket_priority",
    "assign_ticket",
    "close_ticket",
    "delete_ticket",
    "add_ticket_note",
    "create_kb_article",
}

RAG_TOOLS = {"search_knowledge_base"}


def as_sync_tool(src_tool):
    """langchain-mcp-adapters tools are async-only.

    `create_agent` / ToolNode call `.invoke()` on the sync path, which raises
    `NotImplementedError: StructuredTool does not support sync invocation.`
    Wrap each MCP tool so a thread can `asyncio.run(ainvoke(...))`.
    """

    def _run(*args, **kwargs):
        payload = kwargs if kwargs else (args[0] if args else {})
        return run_async(src_tool.ainvoke(payload))

    return StructuredTool.from_function(
        func=_run,
        name=src_tool.name,
        description=src_tool.description or src_tool.name,
        args_schema=getattr(src_tool, "args_schema", None),
    )


async def _aload_mcp_tools(helpdesk_dir: Path):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "helpdesk": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(helpdesk_dir / "mcp_server.py")],
            }
        }
    )
    tools = await client.get_tools()
    return client, [as_sync_tool(t) for t in tools]


def load_mcp_tools(helpdesk_dir: Path | None = None):
    """Start the helpdesk MCP server (stdio) and return (client, tools).

    Keep `client` alive for the life of the process — garbage-collecting it
    kills the subprocess. Tools are sync-wrapped (MCP adapters are async-only).
    """
    helpdesk_dir = helpdesk_dir or find_helpdesk_dir()
    ensure_helpdesk_db(helpdesk_dir)
    return run_async(_aload_mcp_tools(helpdesk_dir))


def split_mcp_tools(tools: list) -> dict[str, list]:
    by_name = {t.name: t for t in tools}
    return {
        "rag": [by_name[n] for n in RAG_TOOLS if n in by_name],
        "sql": [by_name[n] for n in READ_TOOLS if n in by_name],
        "ticket_read": [by_name[n] for n in ("get_ticket", "get_ticket_notes", "search_customers") if n in by_name],
        "ticket_write": [by_name[n] for n in WRITE_TOOLS if n in by_name],
        "all_names": sorted(by_name),
    }


# ── HITL wrapper (same resume shape as notebook 02) -----------------------

def wrap_tool_with_approval(src_tool):
    """Pause before a write. Resume with Command(resume={"approved": True/False})."""

    def _run(**kwargs):
        decision = interrupt(
            {
                "reason": "This action writes to the helpdesk database.",
                "tool": src_tool.name,
                "args": kwargs,
            }
        )
        approved = False
        if isinstance(decision, dict):
            approved = bool(decision.get("approved"))
            decs = decision.get("decisions") or []
            if decs and isinstance(decs[0], dict) and decs[0].get("type") == "approve":
                approved = True
        if not approved:
            return f"Rejected by a human reviewer. `{src_tool.name}` did not run."
        try:
            return src_tool.invoke(kwargs)
        except NotImplementedError:
            return run_async(src_tool.ainvoke(kwargs))

    return StructuredTool.from_function(
        func=_run,
        name=src_tool.name,
        description=(src_tool.description or "") + " Requires human approval before it runs.",
        args_schema=getattr(src_tool, "args_schema", None),
    )


def resume_hitl(approved: bool) -> Command:
    """Resume after HumanInTheLoopMiddleware paused a write.

    Notebook 02 used Command(resume={"approved": True/False}) because
    interrupt() sat in a custom node. Middleware expects:

        Command(resume={"decisions": [{"type": "approve"|"reject"}]})
    """
    return Command(resume={"decisions": [{"type": "approve" if approved else "reject"}]})


def pretty_trace_label(namespace, node_name: str) -> str:
    """Turn a subgraph namespace + node into a classroom-readable path.

    `('knowledge_team:<uuid>', 'rag_agent:<uuid>')` + `tools`
    → `knowledge_team → rag_agent → tools`
    """
    parts: list[str] = []
    for piece in namespace or ():
        head = str(piece).split(":")[0]
        if head and head not in parts:
            parts.append(head)
    short = node_name
    if node_name.startswith("HumanInTheLoop"):
        short = "HITL"
    if short and short not in parts and short != "__interrupt__":
        parts.append(short)
    return " → ".join(parts) or node_name


def enable_langsmith(project: str = "helpdesk-orchestrator") -> dict[str, Any]:
    """Turn on LangSmith if a key is already in the environment.

    Same three-variable pattern as Module 10 Notebook 11. Streamlit and
    Studio call this after load_dotenv so traces land in one project.
    """
    key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not key:
        return {"enabled": False, "project": None, "url": None}
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    proj = os.environ["LANGSMITH_PROJECT"]
    return {
        "enabled": True,
        "project": proj,
        "url": "https://smith.langchain.com",
    }


def invoke_config(thread_id: str, *, run_name: str | None = None) -> dict[str, Any]:
    """thread_id + recursion limit + optional LangSmith run name."""
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }
    if run_name:
        config["run_name"] = run_name
    return config


def json_safe(obj: Any, depth: int = 0) -> Any:
    """Make LangChain objects safe for st.json() / LangGraph Studio panels."""
    if depth > 6:
        return str(obj)[:240]
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): json_safe(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(item, depth + 1) for item in list(obj)[:16]]
    content = getattr(obj, "content", None)
    tool_calls = getattr(obj, "tool_calls", None)
    name = getattr(obj, "name", None)
    if content is not None or tool_calls:
        out: dict[str, Any] = {"type": type(obj).__name__}
        if name:
            out["name"] = name
        if isinstance(content, str):
            out["content"] = content[:800]
        elif content is not None:
            out["content"] = json_safe(content, depth + 1)
        if tool_calls:
            out["tool_calls"] = json_safe(tool_calls, depth + 1)
        return out
    if hasattr(obj, "model_dump"):
        try:
            return json_safe(obj.model_dump(), depth + 1)
        except Exception:  # noqa: BLE001
            pass
    return str(obj)[:400]


def summarize_update(node_output: Any) -> dict[str, Any]:
    """Classroom-readable payload for one stream() tick.

    Supervisor nodes often only update `messages`. Stripping that key left
    `{}` and Streamlit's st.json() then crashed on leftover Message objects
    (`source property must be a valid JSON object`).
    """
    if node_output is None:
        return {"event": "ran"}
    if not isinstance(node_output, dict):
        return {"payload": json_safe(node_output)}

    data: dict[str, Any] = {}
    messages = node_output.get("messages")
    tool_events: list[dict[str, Any]] = []
    last_text = None
    if isinstance(messages, list) and messages:
        last = messages[-1]
        last_text = getattr(last, "content", None)
        if isinstance(last_text, list):
            last_text = " ".join(
                p.get("text", str(p)) if isinstance(p, dict) else str(p) for p in last_text
            )
        if isinstance(last_text, str) and last_text.strip():
            data["last_message"] = last_text[:600]
        for msg in messages:
            for call in getattr(msg, "tool_calls", None) or []:
                if isinstance(call, dict):
                    tool_events.append(
                        {"call": call.get("name"), "args": json_safe(call.get("args"))}
                    )
                else:
                    tool_events.append(
                        {
                            "call": getattr(call, "name", None),
                            "args": json_safe(getattr(call, "args", None)),
                        }
                    )
            msg_type = getattr(msg, "type", None) or type(msg).__name__
            if msg_type in ("tool", "ToolMessage") or type(msg).__name__ == "ToolMessage":
                tool_events.append(
                    {
                        "result": getattr(msg, "name", "tool"),
                        "content": str(getattr(msg, "content", ""))[:500],
                    }
                )
    if tool_events:
        data["tools"] = tool_events

    extra = {
        key: json_safe(value)
        for key, value in node_output.items()
        if key != "messages" and value not in (None, "", [], {})
    }
    if extra:
        data["state"] = extra
    if not data:
        data["event"] = "ran"
    return data


def interrupt_payload(state) -> Any | None:
    """Read the first interrupt payload from a graph snapshot or stream chunk."""
    interrupts = getattr(state, "interrupts", None)
    if interrupts:
        first = interrupts[0]
        return getattr(first, "value", first)
    tasks = getattr(state, "tasks", None) or ()
    for task in tasks:
        for item in getattr(task, "interrupts", ()) or ():
            return getattr(item, "value", item)
    return None


# ── Web search ------------------------------------------------------------

@tool
def web_search(query: str) -> str:
    """Search the public web. Use for current events and facts NOT in the company knowledge base."""
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
            "Set TAVILY_API_KEY or `pip install ddgs`."
        )


# ── Store tools -----------------------------------------------------------

def make_store_tools(store: InMemoryStore, user_id: str) -> list:
    @tool
    def recall_answer_style() -> str:
        """Read this user's preferred answer style: concise or detailed."""
        item = store.get(("preferences", user_id), "answer_style")
        return item.value["value"] if item else "detailed"

    @tool
    def set_answer_style(style: str) -> str:
        """Save this user's answer style. Must be 'concise' or 'detailed'."""
        if style not in ("concise", "detailed"):
            return "style must be concise or detailed"
        store.put(("preferences", user_id), "answer_style", {"value": style})
        return f"Saved answer style: {style}"

    return [recall_answer_style, set_answer_style]


def remember_answer_style(store: InMemoryStore, user_id: str, style: str) -> None:
    if style not in ("concise", "detailed"):
        raise ValueError("style must be 'concise' or 'detailed'")
    store.put(("preferences", user_id), "answer_style", {"value": style})


def make_desk_helpers(helpdesk_dir: Path) -> list:
    """One extra read tool the MCP server does not expose: the full ticket board.

    LangSmith traces showed the supervisor saying "I am unable to display all
    tickets" because there is no list_all_tickets MCP tool — only
    list_tickets_by_customer / list_tickets_by_agent. This helper reads the
    same helpdesk.db. It does not rebuild the server.
    """
    db_path = str(helpdesk_dir / "helpdesk.db")

    @tool
    def list_all_tickets() -> str:
        """List EVERY ticket on the helpdesk (id, status, priority, subject, customer, agent).

        Use when the user says all tickets, every ticket, the ticket board,
        or 'display tickets for me' without naming a customer.
        """
        import sqlite3

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT t.id, t.status, t.priority, t.subject,
                   c.name AS customer, a.name AS agent
            FROM tickets t
            JOIN customers c ON c.id = t.customer_id
            LEFT JOIN agents a ON a.id = t.agent_id
            ORDER BY t.id
            """
        ).fetchall()
        con.close()
        if not rows:
            return "No tickets in the database."
        lines = [
            f"- #{r['id']} [{r['status']}/{r['priority']}] {r['subject']} "
            f"— customer={r['customer']} agent={r['agent'] or 'unassigned'}"
            for r in rows
        ]
        return f"{len(rows)} tickets:\n" + "\n".join(lines)

    @tool
    def list_all_agents() -> str:
        """List every support agent (name and team). Use for 'agent names' / who works here."""
        import sqlite3

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT name, team FROM agents ORDER BY team, name"
        ).fetchall()
        con.close()
        if not rows:
            return "No agents in the database."
        lines = [f"- {r['name']} ({r['team']})" for r in rows]
        return f"{len(rows)} agents:\n" + "\n".join(lines)

    return [list_all_tickets, list_all_agents]


_PLACEHOLDER = (
    "please hold on",
    "hold on for a moment",
    "while i gather",
    "i need to gather",
    "i am unable",
    "unable to provide",
    "unable to display",
    "i have provided",
    "the team has provided",
    "the ops team has provided",
    "successfully transferred",
    "i transferred",
    "need your name",
    "please provide your name",
    "please provide it",
)


def _message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("text"):
                parts.append(str(part["text"]))
        return " ".join(parts)
    return str(content)


def _last_human_text(messages: list) -> str:
    for msg in reversed(messages or []):
        kind = getattr(msg, "type", None)
        if kind in ("human", "user"):
            return _message_text(getattr(msg, "content", ""))
    return ""


def is_placeholder_answer(text: str) -> bool:
    t = _message_text(text).lower().strip()
    if not t:
        return True
    return any(needle in t for needle in _PLACEHOLDER)


def make_fill_placeholder_hook(desk_helpers: list):
    """If a supervisor says 'please hold on' / 'unable' with no tool call, fill from SQLite.

    LangSmith: ops_supervisor returned 'please hold on' and never called sql_agent.
    Prompts do not stop that. This hook is deterministic.
    """
    helpers = {t.name: t for t in desk_helpers}

    def post_model_hook(state: dict) -> dict:
        msgs = state.get("messages") or []
        last = msgs[-1] if msgs else None
        if last is None or getattr(last, "tool_calls", None):
            return {}
        content = getattr(last, "content", "")
        if not is_placeholder_answer(content):
            return {}
        q = _last_human_text(msgs).lower()
        if "agent" in q and "ticket" not in q:
            tool_name = "list_all_agents"
        elif "ticket" in q:
            tool_name = "list_all_tickets"
        else:
            return {}
        helper = helpers.get(tool_name)
        if helper is None:
            return {}
        board = helper.invoke({})
        return {"messages": [AIMessage(content=board)]}

    return post_model_hook


# ── Agents ----------------------------------------------------------------

def _agent(llm, tools, name: str, prompt: str, middleware=None):
    """create_agent with a stable name so create_supervisor can address it."""
    kwargs = dict(model=llm, tools=tools, name=name)
    if middleware:
        kwargs["middleware"] = list(middleware)
    try:
        return create_agent(**kwargs, system_prompt=prompt)
    except TypeError:
        return create_agent(**kwargs, prompt=prompt)


def build_specialists(llm, buckets: dict[str, list], extra_sql: list | None = None):
    """Four named agents. Ticket writes pause via HumanInTheLoopMiddleware."""
    rag_tools = buckets["rag"]
    sql_tools = list(buckets["sql"]) + list(extra_sql or [])
    # interrupt() *inside* a tool does not pause: ToolNode runs tools on a
    # thread pool, and GraphInterrupt never reaches the checkpointer.
    # HumanInTheLoopMiddleware pauses in the agent node, before the write runs.
    from langchain.agents.middleware import HumanInTheLoopMiddleware

    hitl = HumanInTheLoopMiddleware(
        interrupt_on={t.name: True for t in buckets["ticket_write"]}
    )
    ticket_tools = buckets["ticket_read"] + buckets["ticket_write"]

    rag_agent = _agent(
        llm,
        rag_tools,
        "rag_agent",
        "You answer company policy and how-to questions from the knowledge base. "
        "Always call search_knowledge_base before you answer. Quote the article. "
        "Never invent policy. Never say 'I have provided the policy' without quoting it. "
        "If the question is about customers, agents, tickets, or a person's "
        "name (Jane, Aisha, Maria…), say so — that is ops, not RAG.",
    )
    search_agent = _agent(
        llm,
        [web_search],
        "search_agent",
        "You MUST call web_search before answering. Quote the results. "
        "Do not invent news. Do not answer internal policy or ticket questions.",
    )
    sql_agent = _agent(
        llm,
        sql_tools,
        "sql_agent",
        "You READ the helpdesk database. Always call a tool. Never say you are "
        "unable to provide information — a tool exists for every lookup. "
        "Rules:\n"
        "- Agent names / who works here / list agents → list_agents.\n"
        "- A first name like Aisha, Maria, Priya is usually an AGENT — "
        "list_agents, then list_tickets_by_agent. Do not search_customers first.\n"
        "- A full customer name (Jane Doe) → search_customers, then "
        "list_tickets_by_customer.\n"
        "- 'all tickets' / 'tickets for me' / the whole board → list_all_tickets.\n"
        "- Workload / who is busiest → get_agent_workload.\n"
        "If the user wants to change a ticket or add a note, say ticket_agent must do it.",
    )
    ticket_agent = _agent(
        llm,
        ticket_tools,
        "ticket_agent",
        "You create, update, close, or annotate tickets. You MUST call a write tool — "
        "never claim you added a note unless the tool returned success. "
        "Look up the ticket or customer first. After a rejection, do not claim the write happened.",
        middleware=[hitl],
    )
    return {
        "rag_agent": rag_agent,
        "search_agent": search_agent,
        "sql_agent": sql_agent,
        "ticket_agent": ticket_agent,
    }


def _compile_supervisor(
    agents: list,
    llm,
    *,
    supervisor_name: str,
    prompt: str,
    extra_tools=None,
    post_model_hook=None,
):
    from langgraph_supervisor import create_supervisor

    kwargs: dict[str, Any] = dict(
        model=llm,
        prompt=prompt,
        supervisor_name=supervisor_name,
        output_mode="last_message",
        include_agent_name="inline",
        add_handoff_back_messages=True,
    )
    if extra_tools:
        kwargs["tools"] = extra_tools
    if post_model_hook:
        kwargs["post_model_hook"] = post_model_hook
    return create_supervisor(agents, **kwargs).compile(name=supervisor_name.replace("_supervisor", "_team") if supervisor_name.endswith("_supervisor") else supervisor_name)


def build_orchestrator(
    model: str = "gpt-4o-mini",
    helpdesk_dir: Path | None = None,
    user_id: str = "default-user",
    mcp_client_and_tools: tuple | None = None,
    for_studio: bool = False,
):
    """Build the hierarchical graph.

    Returns a dict: graph, store, mcp_client, tool_names, specialists, helpdesk_dir.

    `for_studio=True` compiles without our own checkpointer — LangGraph Studio
    (`langgraph dev`) injects the platform saver so HITL still pauses.
    """
    helpdesk_dir = helpdesk_dir or find_helpdesk_dir()
    ensure_helpdesk_db(helpdesk_dir)

    if mcp_client_and_tools is None:
        client, tools = load_mcp_tools(helpdesk_dir)
    else:
        client, tools = mcp_client_and_tools

    buckets = split_mcp_tools(tools)
    llm = ChatOpenAI(model=model, temperature=0)
    store = InMemoryStore()
    store_tools = make_store_tools(store, user_id)
    desk_helpers = make_desk_helpers(helpdesk_dir)
    fill_placeholder = make_fill_placeholder_hook(desk_helpers)
    specialists = build_specialists(llm, buckets, extra_sql=desk_helpers)

    knowledge_team = _compile_supervisor(
        [specialists["rag_agent"], specialists["search_agent"]],
        llm,
        supervisor_name="knowledge_supervisor",
        prompt=(
            "You run the knowledge desk. Always delegate. Never answer yourself. "
            "Policy / how-to / refund / cancellation / password / 2FA → rag_agent. "
            "Current events / public facts / 'what is LangGraph' / latest news → search_agent. "
            "Customers, agents, tickets, names of people → this is NOT your desk. "
            "Say 'ops_team handles that' and stop. Do not invent a refusal. "
            "Return the specialist's facts to the parent."
        ),
    )
    ops_team = _compile_supervisor(
        [specialists["sql_agent"], specialists["ticket_agent"]],
        llm,
        supervisor_name="ops_supervisor",
        prompt=(
            "You run the operations desk. Always delegate. Never answer yourself. "
            "Never say 'I am unable to display' — sql_agent can list agents, "
            "tickets for a person, or ALL tickets. "
            "Lookups, counts, lists, history, workload, 'display tickets' → sql_agent. "
            "Create / update / close / add a note → ticket_agent. "
            "Do not invent ticket ids. "
            "Your last message must BE the specialist's list (every ticket / name). "
            "Never replace it with 'I have provided' or 'sql_agent handled it'. "
            "Never say please hold on / gathering / wait. "
            "Show/list/display tickets THIS turn → transfer_to_sql_agent or list_all_tickets."
        ),
        extra_tools=desk_helpers,
        post_model_hook=fill_placeholder,
    )
    from langgraph_supervisor import create_supervisor

    # Parent checkpointer is required for interrupt() inside ticket_agent.
    top_builder = create_supervisor(
        [knowledge_team, ops_team],
        model=llm,
        prompt=(
            "You are the helpdesk orchestrator. You NEVER answer from memory "
            "and you NEVER refuse a lookup. "
            "Policy, how-to, docs, public-web facts → knowledge_team. "
            "Customers, agents, tickets, names (Jane, Aisha), lists, SQL, notes, writes → ops_team. "
            "'Display all tickets' / 'list the agents' / a first name → ops_team. "
            "Wait for the team. Your final reply MUST contain their actual list or quote — "
            "copy every ticket line / agent name. "
            "Never say 'I am unable', 'I have provided', 'the team has provided', or 'I transferred'. "
            "If the user asks 'why don't you show X', show X now — do not apologize. "
            "Never say please hold on, gathering, or wait — either call a team or "
            "output the list. "
            "A question can need both desks — call them in order. "
            "Call recall_answer_style if you need this user's verbosity."
        ),
        supervisor_name="top_supervisor",
        output_mode="last_message",
        include_agent_name="inline",
        add_handoff_back_messages=True,
        tools=store_tools,
        post_model_hook=fill_placeholder,
    )
    compile_kwargs: dict[str, Any] = {"name": "helpdesk_orchestrator"}
    if not for_studio:
        # Studio / `langgraph dev` injects its own saver + store. Passing
        # InMemoryStore here makes the API refuse to load the graph.
        compile_kwargs["checkpointer"] = InMemorySaver()
        compile_kwargs["store"] = store
    graph = top_builder.compile(**compile_kwargs)

    return {
        "graph": graph,
        "store": store,
        "mcp_client": client,
        "tool_names": buckets["all_names"] + [t.name for t in desk_helpers],
        "specialists": specialists,
        "teams": {"knowledge_team": knowledge_team, "ops_team": ops_team},
        "helpdesk_dir": helpdesk_dir,
        "buckets": buckets,
    }
