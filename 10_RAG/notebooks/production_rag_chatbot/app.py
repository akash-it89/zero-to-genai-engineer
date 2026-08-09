"""
Production RAG Chatbot — Streamlit UI

Wraps ProductionRAGChatbot (rag_pipeline.py) — the exact pipeline built in
Notebook 13 — in a chat interface: upload your own document(s), tune the
retrieval/guardrail settings in the sidebar, then chat with citations.

One message, two answers: every question also runs through naive_chat() —
the same Section 2 "cold open" baseline (top-1, dense-only, no rerank, no
guardrail, no citations) — reusing the SAME index, so the only variable is
the retrieval/generation strategy. Side by side, live, on your own document.

Run with:
    streamlit run app.py
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# rag_pipeline.py lives next to this file.
sys.path.insert(0, str(Path(__file__).parent))
from rag_pipeline import ProductionRAGChatbot

# .env lives two levels up (10_RAG/.env), same as every notebook in this series.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

st.set_page_config(page_title="Production RAG Chatbot", page_icon="📚", layout="wide")

# ---- Session state -----------------------------------------------------
if "bot" not in st.session_state:
    st.session_state.bot = None
if "turns" not in st.session_state:
    st.session_state.turns = []              # [{"question", "naive", "production"}]
if "doc_names" not in st.session_state:
    st.session_state.doc_names = []

# ---- Sidebar: upload + pipeline settings --------------------------------
with st.sidebar:
    st.header("📚 Knowledge base")

    uploaded_files = st.file_uploader(
        "Upload document(s)",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="Everything you upload gets pooled into one hybrid index.",
    )

    st.subheader("Pipeline settings")
    chunk_size = st.slider("Chunk size (characters)", 200, 1500, 500, step=50)
    chunk_overlap = st.slider("Chunk overlap", 0, 300, 80, step=10)
    top_k = st.slider("Candidates after fusion (top-k)", 4, 20, 8)
    top_n = st.slider("Chunks sent to the LLM after rerank (top-n)", 1, 8, 4)
    min_rerank_score = st.slider(
        "Groundedness threshold (min rerank score)", -12.0, 5.0, -9.5, step=0.5,
        help=(
            "Below this, the bot refuses instead of guessing. For ms-marco-MiniLM, clearly "
            "irrelevant queries floor out around -11; on-topic ones (even vague summaries) "
            "usually land above -10. Calibrate on your own corpus."
        ),
    )

    build_clicked = st.button("🔨 Build / rebuild index", type="primary", use_container_width=True)

    st.divider()
    st.subheader("Comparison")
    compare_naive = st.checkbox(
        "Show naive RAG side by side", value=True,
        help="Every question also runs through the Section 2 top-1/no-guardrail baseline, "
             "on the same index, so you can watch the two answers diverge live.",
    )

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.turns = []
        if st.session_state.bot is not None:
            st.session_state.bot.history = []
        st.rerun()

# ---- Build / rebuild the index -----------------------------------------
if build_clicked:
    if not uploaded_files:
        st.sidebar.error("Upload at least one file first.")
    else:
        with st.spinner("Parsing, chunking, embedding, and indexing..."):
            tmp_dir = Path(tempfile.mkdtemp())
            saved_paths = []
            for f in uploaded_files:
                dest = tmp_dir / f.name
                dest.write_bytes(f.getvalue())
                saved_paths.append(str(dest))

            bot = ProductionRAGChatbot(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                top_k=top_k,
                top_n=top_n,
                min_rerank_score=min_rerank_score,
            )
            stats = bot.ingest(saved_paths)

            st.session_state.bot = bot
            st.session_state.doc_names = [f.name for f in uploaded_files]
            st.session_state.turns = []
        names = ", ".join(st.session_state.doc_names)
        st.sidebar.success(f"Indexed **{names}** — {stats['pages']} page(s), {stats['chunks']} chunks")

# ---- Main -----------------------------------------------------------------
st.title("📚 Production RAG Chatbot")
st.caption(
    "Hybrid retrieval (dense + BM25, RRF-fused) → cross-encoder rerank → grounded, "
    "cited generation → groundedness guardrail → conversational memory."
)

if st.session_state.bot is None:
    st.info("👈 Upload a document and click **Build / rebuild index** to get started.")
    st.stop()

# Always-visible banner: which document(s) the CURRENT index was built from. This is the
# single most common source of confusion in a live demo — asking a question that belongs
# to a different document than the one currently loaded, and getting a correct-looking
# "I don't have that information" from BOTH bots because neither has it, not because the
# guardrail is doing anything interesting.
doc_list = ", ".join(st.session_state.doc_names) or "unknown"
st.markdown(
    f"""<div style="background-color:#1f2937;color:#e5e7eb;padding:0.6rem 1rem;
    border-radius:0.5rem;border-left:4px solid #38bdf8;margin-bottom:1rem;font-size:0.95rem;">
    📄 <strong>Currently indexed:</strong> {doc_list}
    </div>""",
    unsafe_allow_html=True,
)


def render_naive(naive):
    st.markdown("##### 🔴 Naive RAG")
    st.caption("Top-1 · dense-only · no rerank · no guardrail · no citations · no memory")
    st.markdown(naive["answer"])
    st.caption(f"Retrieved: {naive['source']['source']}, p.{naive['source']['page']}")


def render_production(prod, question):
    st.markdown("##### 🟢 Production RAG")
    st.caption("Hybrid + RRF → reranked → guardrail → cited → memory-aware")
    st.markdown(prod["answer"])
    if prod["standalone_question"] != question:
        st.caption(f"Resolved follow-up to: *{prod['standalone_question']}*")
    if prod["sources"]:
        with st.expander(f"📎 {len(prod['sources'])} source(s)"):
            for s in prod["sources"]:
                st.markdown(f"**[{s['rank']}] {s['source']}, p.{s['page']}** — score {s['score']}")
                st.caption(s["text"][:400] + ("…" if len(s["text"]) > 400 else ""))


# ---- Replay history ---------------------------------------------------
for turn in st.session_state.turns:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        if turn["naive"] is not None:
            col1, col2 = st.columns(2)
            with col1:
                render_naive(turn["naive"])
            with col2:
                render_production(turn["production"], turn["question"])
        else:
            render_production(turn["production"], turn["question"])

# ---- New message --------------------------------------------------------
chat_placeholder = f"Ask something about {', '.join(st.session_state.doc_names)}..."
question = st.chat_input(chat_placeholder)
if question:
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if compare_naive:
            col1, col2 = st.columns(2)
            with col1:
                with st.spinner("Naive RAG (top-1)..."):
                    naive_result = st.session_state.bot.naive_chat(question)
                render_naive(naive_result)
            with col2:
                with st.spinner("Production RAG (hybrid → rerank → cite)..."):
                    prod_result = st.session_state.bot.chat(question)
                render_production(prod_result, question)
        else:
            naive_result = None
            with st.spinner("Retrieving → reranking → generating..."):
                prod_result = st.session_state.bot.chat(question)
            render_production(prod_result, question)

    st.session_state.turns.append(
        {"question": question, "naive": naive_result, "production": prod_result}
    )
