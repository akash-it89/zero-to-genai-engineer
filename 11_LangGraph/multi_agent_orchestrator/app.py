"""
Hierarchical helpdesk orchestrator — Streamlit UI.

Run:
    cd 11_LangGraph/multi_agent_orchestrator
    python3 -m streamlit run app.py
"""

import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "10_RAG" / ".env")
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from graph import (  # noqa: E402
    build_orchestrator,
    enable_langsmith,
    interrupt_payload,
    invoke_config,
    json_safe,
    pretty_trace_label,
    remember_answer_style,
    resume_hitl,
    summarize_update,
)

st.set_page_config(page_title="Helpdesk Orchestrator", page_icon="🎧", layout="wide")

LANGSMITH = enable_langsmith()


@st.cache_resource(show_spinner="Starting MCP server and indexing the knowledge base…")
def get_bundle():
    return build_orchestrator(user_id="default-user")


bundle = get_bundle()
graph = bundle["graph"]
store = bundle["store"]

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "ticket-desk-1"
if "turns" not in st.session_state:
    st.session_state.turns = []
if "pending" not in st.session_state:
    st.session_state.pending = None


def _config(run_name: str | None = None):
    return invoke_config(st.session_state.thread_id, run_name=run_name)


def run_turn(payload, run_name: str):
    trace = []
    for item in graph.stream(
        payload, _config(run_name), stream_mode="updates", subgraphs=True
    ):
        ns, update = item if isinstance(item, tuple) and len(item) == 2 else ((), item)
        for node_name, node_output in update.items():
            if node_name == "__interrupt__":
                value = json_safe(node_output[0].value if node_output else {})
                if st.session_state.pending is None:
                    st.session_state.pending = {"payload": value}
                    trace.append({"node": "PAUSED", "data": {"interrupt": value}})
                continue
            label = pretty_trace_label(ns, node_name)
            data = summarize_update(node_output)
            if not trace or trace[-1]["node"] != label or trace[-1]["data"] != data:
                trace.append({"node": label, "data": data})
    snap = graph.get_state(_config())
    pending = interrupt_payload(snap)
    if pending is not None:
        pending = json_safe(pending)
        st.session_state.pending = {"payload": pending}
        if not any(step["node"] == "PAUSED" for step in trace):
            trace.append({"node": "PAUSED", "data": {"interrupt": pending}})
        return trace, None
    st.session_state.pending = None
    answer = None
    messages = (snap.values or {}).get("messages") or []
    if messages:
        answer = getattr(messages[-1], "content", str(messages[-1]))
        if isinstance(answer, list):
            answer = " ".join(
                p.get("text", str(p)) if isinstance(p, dict) else str(p) for p in answer
            )
    return trace, answer


def render_trace(trace: list):
    if not trace:
        st.caption("No graph ticks on this turn.")
        return
    rows = []
    for step in trace:
        data = step.get("data") or {}
        tools = data.get("tools") or []
        calls = ", ".join(
            t.get("call") or t.get("result") or "" for t in tools if isinstance(t, dict)
        )
        snippet = data.get("last_message") or data.get("event") or ""
        if data.get("interrupt"):
            snippet = "waiting for human approval"
        rows.append(
            {
                "path": step["node"],
                "tools": calls,
                "what happened": (snippet[:160] + "…") if len(str(snippet)) > 160 else snippet,
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)
    with st.expander("Raw tick payloads (JSON-safe)"):
        for step in trace:
            st.markdown(f"**{step['node']}**")
            st.json(step["data"] if isinstance(step["data"], (dict, list)) else {"payload": step["data"]})


with st.sidebar:
    st.header("Thread")
    st.caption("Same thread_id = same checkpointer whiteboard. A new id is a new ticket.")
    st.session_state.thread_id = st.text_input("thread_id", st.session_state.thread_id)
    if st.button("New thread"):
        st.session_state.thread_id = f"ticket-desk-{uuid.uuid4().hex[:6]}"
        st.session_state.pending = None
        st.rerun()

    st.header("Answer style (Store)")
    style = st.radio("Remembered across threads", ["detailed", "concise"], index=0)
    if st.button("Save style"):
        remember_answer_style(store, "default-user", style)
        st.success(f"Saved: {style}")

    st.header("Observability")
    if LANGSMITH["enabled"]:
        st.success(f"LangSmith project: `{LANGSMITH['project']}`")
        st.markdown(f"[Open LangSmith]({LANGSMITH['url']})")
        st.caption("Every turn is a traced run — supervisors, MCP tools, RAG, web.")
    else:
        st.warning("LangSmith is off. Set LANGSMITH_API_KEY + LANGSMITH_TRACING=true.")
    st.caption("LangGraph Studio: `langgraph dev` then open the Studio URL it prints.")

    st.header("MCP tools")
    st.caption(f"{len(bundle['tool_names'])} tools from the helpdesk server")
    st.code("\n".join(bundle["tool_names"]), language="text")

    st.header("Try")
    st.markdown(
        "- What is our refund policy?\n"
        "- How many tickets has Jane Doe opened?\n"
        "- Search the web: what is LangGraph used for?\n"
        "- Add a note to Jane Doe's latest ticket that we offered a refund"
    )

st.title("Helpdesk orchestrator")
st.caption("Hierarchical LangGraph — knowledge desk (RAG + web) and ops desk (SQL + tickets). Writes wait for you.")

for turn in st.session_state.turns:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        if turn.get("trace"):
            with st.expander("Trace — which agent fired", expanded=True):
                render_trace(turn["trace"])
        if turn.get("answer"):
            st.write(turn["answer"])

if st.session_state.pending:
    payload = st.session_state.pending["payload"]
    st.warning("Human review — nothing has been written yet.")
    st.json(payload if isinstance(payload, (dict, list)) else {"payload": payload})
    c1, c2 = st.columns(2)
    if c1.button("Yes — approve", type="primary"):
        trace, answer = run_turn(resume_hitl(True), "hitl-approve")
        st.session_state.turns.append(
            {"question": "(approved write)", "trace": trace, "answer": answer}
        )
        st.session_state.pending = None
        st.rerun()
    if c2.button("No — reject"):
        trace, answer = run_turn(resume_hitl(False), "hitl-reject")
        st.session_state.turns.append(
            {"question": "(rejected write)", "trace": trace, "answer": answer}
        )
        st.session_state.pending = None
        st.rerun()
else:
    question = st.chat_input("Ask the helpdesk…")
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.spinner("Routing through the teams…"):
            trace, answer = run_turn(
                {"messages": [HumanMessage(content=question)]},
                question[:80],
            )
        st.session_state.turns.append({"question": question, "trace": trace, "answer": answer})
        st.rerun()
