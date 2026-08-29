"""
Self-Correcting Agentic RAG -- Streamlit UI

Wraps the LangGraph agent built in Notebook 03 (graph.py) in a chat interface: upload a
document, chat with it, and watch the agent's trace -- which nodes fired, how many times it
retried a weak retrieval or an ungrounded answer, and whether it had to pause and hand off to
a human. Optionally compares every answer, side by side, against Module 10's straight-line
`ProductionRAGChatbot` on the exact same document -- so the difference a graph makes is
visible, not just asserted.

Run with:
    streamlit run app.py
"""

import sys
import tempfile
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_REPO_ROOT / "10_RAG" / ".env")
load_dotenv(_REPO_ROOT / "11_LangGraph" / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from graph import build_graph, remember_answer_style, extract_structured_citations  # noqa: E402

RAG_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "10_RAG" / "notebooks" / "production_rag_chatbot"
sys.path.insert(0, str(RAG_PIPELINE_DIR))
from rag_pipeline import ProductionRAGChatbot  # noqa: E402

from langchain_core.messages import HumanMessage  # noqa: E402
from langgraph.types import Command  # noqa: E402

st.set_page_config(page_title="Self-Correcting Agentic RAG", page_icon="🧠", layout="wide")

USER_ID = "default-user"   # long-term Store memory (answer_style) is keyed by this, not by thread_id


@st.cache_resource(show_spinner=False)
def get_graph_bundle():
    return build_graph(user_id=USER_ID)


# ---- Session state -----------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "turns" not in st.session_state:
    st.session_state.turns = []           # [{"question", "trace", "answer", "compare"}]
if "pending_interrupt" not in st.session_state:
    st.session_state.pending_interrupt = None   # {"payload": ..., "question": ...}
if "compare_bot" not in st.session_state:
    st.session_state.compare_bot = None
if "doc_names" not in st.session_state:
    st.session_state.doc_names = []

graph, index, reranker, store, ingest = get_graph_bundle()

# ---- Sidebar -------------------------------------------------------------
with st.sidebar:
    st.header("📚 Knowledge base")
    st.caption("Starts pre-loaded with Module 10's `sample_report.pdf`. Upload your own to replace it.")

    uploaded_files = st.file_uploader(
        "Upload document(s)", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True
    )
    if st.button("🔨 Rebuild index from uploads", use_container_width=True):
        if not uploaded_files:
            st.error("Upload at least one file first.")
        else:
            with st.spinner("Parsing, chunking, embedding, indexing..."):
                tmp_dir = Path(tempfile.mkdtemp())
                saved_paths = []
                for f in uploaded_files:
                    dest = tmp_dir / f.name
                    dest.write_bytes(f.getvalue())
                    saved_paths.append(str(dest))
                stats = ingest(saved_paths)
                st.session_state.doc_names = [f.name for f in uploaded_files]
                st.session_state.turns = []
                st.session_state.pending_interrupt = None
                st.session_state.thread_id = str(uuid.uuid4())
                if compare_enabled := st.session_state.get("compare_enabled"):
                    bot = ProductionRAGChatbot()
                    bot.ingest(saved_paths)
                    st.session_state.compare_bot = bot
            st.success(f"Indexed {stats['pages']} page(s), {stats['chunks']} chunks")

    st.divider()
    st.subheader("Answer style (long-term memory)")
    st.caption(
        "Stored in the graph's `Store`, keyed by user -- not by conversation. Change it, start "
        "a brand-new conversation below, and the new thread still recalls it. Same mechanism "
        "as Notebook 11 §6's `@dynamic_prompt` + `Store`, applied as a plain key lookup here."
    )
    answer_style = st.radio("Preferred verbosity", ["detailed", "concise"], horizontal=True, key="answer_style_choice")
    if st.button("💾 Remember this preference", use_container_width=True):
        remember_answer_style(store, USER_ID, answer_style)
        st.success(f"Stored: future answers for '{USER_ID}' will be {answer_style} -- even in a new thread.")

    st.divider()
    st.subheader("Comparison")
    compare_enabled = st.checkbox(
        "Compare against Module 10's straight-line chatbot", value=False, key="compare_enabled",
        help="Runs the exact same question through ProductionRAGChatbot.chat() (rag_pipeline.py, "
             "no retry loop, no self-grading, no human escalation) so you can see what the graph adds.",
    )

    st.divider()
    if st.button("🗑️ New conversation", use_container_width=True):
        st.session_state.turns = []
        st.session_state.pending_interrupt = None
        st.session_state.thread_id = str(uuid.uuid4())
        if st.session_state.compare_bot is not None:
            st.session_state.compare_bot.history = []
        st.rerun()

# ---- Main -----------------------------------------------------------------
st.title("🧠 Self-Correcting Agentic RAG")
st.caption(
    "trim history → recall preferences → condense → retrieve → grade → (rewrite ↺) → generate "
    "→ check groundedness (RAGAS) → (regenerate ↺) → human escalation (⏸ interrupt) → finalize "
    "— built on Module 10's hybrid retrieval + reranking, unmodified."
)

doc_label = ", ".join(st.session_state.doc_names) or "sample_report.pdf (Module 10 default)"
st.markdown(
    f"""<div style="background-color:#1f2937;color:#e5e7eb;padding:0.6rem 1rem;
    border-radius:0.5rem;border-left:4px solid #38bdf8;margin-bottom:1rem;font-size:0.95rem;">
    📄 <strong>Currently indexed:</strong> {doc_label}
    </div>""",
    unsafe_allow_html=True,
)


def render_trace(trace):
    with st.expander(f"🔍 Agent trace ({len(trace)} node(s) fired)"):
        for node_name, output in trace:
            shown = {k: v for k, v in output.items() if k != "messages"}
            st.markdown(f"**{node_name}** → `{shown}`")


def render_agentic_answer(turn, turn_key):
    st.markdown("##### 🟢 Self-Correcting Agentic RAG (M11)")
    st.markdown(turn["answer"])
    badge = {
        "grounded": "✅ grounded", "human_provided": "🧑 human-provided",
        "refused": "🚫 refused (no grounded answer found)", "not_grounded": "⚠️ not grounded",
    }.get(turn.get("groundedness"), "")
    score = turn.get("faithfulness_score")
    if score is not None:
        badge += f"  ·  RAGAS faithfulness: {score:.2f}"
    if badge:
        st.caption(badge)
    render_trace(turn["trace"])

    if turn.get("reranked"):
        if st.button("🧾 Extract structured citations", key=f"structured-{turn_key}"):
            with st.spinner("llm.with_structured_output() -- Notebook 11 §11 pattern..."):
                structured = extract_structured_citations(
                    question=turn.get("standalone_question") or turn["question"],
                    answer=turn["answer"],
                    reranked=turn["reranked"],
                )
            st.json(structured.model_dump())


def render_compare_answer(compare):
    st.markdown("##### 🔴 Straight-line RAG (M10, no retry/self-check/escalation)")
    st.markdown(compare["answer"])
    if compare["sources"]:
        with st.expander(f"📎 {len(compare['sources'])} source(s)"):
            for s in compare["sources"]:
                st.caption(f"[{s['rank']}] {s['source']} p.{s['page']} — score {s['score']}")


def run_turn(question: str):
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    trace = []
    interrupted_payload = None
    for update in graph.stream({"messages": [HumanMessage(content=question)]}, config, stream_mode="updates"):
        for node_name, output in update.items():
            if node_name == "__interrupt__":
                interrupted_payload = output[0].value
                continue
            trace.append((node_name, output))

    if interrupted_payload is not None:
        st.session_state.pending_interrupt = {
            "payload": interrupted_payload, "question": question, "trace": trace, "config": config,
        }
        return None

    final_state = graph.get_state(config).values
    return {
        "answer": final_state.get("answer"),
        "groundedness": final_state.get("groundedness"),
        "faithfulness_score": final_state.get("faithfulness_score"),
        "standalone_question": final_state.get("standalone_question"),
        "reranked": final_state.get("reranked"),
        "trace": trace,
    }


# ---- Human-in-the-loop approval box ---------------------------------------
if st.session_state.pending_interrupt is not None:
    pending = st.session_state.pending_interrupt
    st.warning("⏸ **The agent paused and is asking for human input.**")
    payload = pending["payload"]
    st.markdown(f"**Reason:** {payload['reason']}")
    st.markdown(f"**Question:** {payload['question']}")
    st.caption(
        f"Retries used — rewrites: {payload['rewrite_count']}, regenerations: {payload['regenerate_count']}"
    )
    if payload.get("best_effort_answer"):
        st.caption(f"Best-effort (unconfirmed) answer: {payload['best_effort_answer']}")

    human_answer = st.text_area(
        "Provide the correct answer (or leave blank to let the agent give its honest refusal):",
        key="human_answer_input",
    )
    def _resume_turn(resume_value, escalation_note):
        resumed = graph.invoke(Command(resume=resume_value), pending["config"])
        state = graph.get_state(pending["config"]).values
        turn = {
            "question": pending["question"],
            "answer": resumed["messages"][-1].content,
            "groundedness": state.get("groundedness"),
            "faithfulness_score": state.get("faithfulness_score"),
            "standalone_question": state.get("standalone_question"),
            "reranked": state.get("reranked"),
            "trace": pending["trace"] + [("human_escalation", escalation_note), ("finalize", {})],
        }
        if st.session_state.compare_bot is not None:
            turn["compare"] = st.session_state.compare_bot.chat(pending["question"])
        st.session_state.turns.append(turn)
        st.session_state.pending_interrupt = None
        st.rerun()

    col1, col2 = st.columns(2)
    if col1.button("✅ Submit guidance", type="primary", use_container_width=True):
        _resume_turn({"human_answer": human_answer or None}, {"human_answer": human_answer or None})
    if col2.button("🚫 Let the agent refuse", use_container_width=True):
        _resume_turn({"human_answer": None}, {})
    st.stop()

# ---- Replay history ---------------------------------------------------
for i, turn in enumerate(st.session_state.turns):
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        if turn.get("compare") is not None:
            col1, col2 = st.columns(2)
            with col1:
                render_compare_answer(turn["compare"])
            with col2:
                render_agentic_answer(turn, turn_key=i)
        else:
            render_agentic_answer(turn, turn_key=i)

# ---- New message --------------------------------------------------------
question = st.chat_input(f"Ask something about {doc_label}...")
if question:
    if compare_enabled and st.session_state.compare_bot is None:
        default_report = Path(__file__).resolve().parents[2] / "10_RAG" / "notebooks" / "data" / "sample_report.pdf"
        bot = ProductionRAGChatbot()
        bot.ingest([str(default_report)])
        st.session_state.compare_bot = bot

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("condense → retrieve → grade → generate → check groundedness..."):
            result = run_turn(question)

        if result is None:
            st.rerun()  # pending_interrupt is now set; rerun to show the approval box
        else:
            compare_result = None
            if compare_enabled:
                with st.spinner("Running Module 10's straight-line chatbot for comparison..."):
                    compare_result = st.session_state.compare_bot.chat(question)

            turn = {"question": question, "compare": compare_result, **result}
            new_turn_key = len(st.session_state.turns)
            if compare_result is not None:
                col1, col2 = st.columns(2)
                with col1:
                    render_compare_answer(compare_result)
                with col2:
                    render_agentic_answer(turn, turn_key=new_turn_key)
            else:
                render_agentic_answer(turn, turn_key=new_turn_key)
            st.session_state.turns.append(turn)
