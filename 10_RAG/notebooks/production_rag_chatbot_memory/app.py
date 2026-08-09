"""
Production RAG Chatbot + Memory — Streamlit UI

Wraps the agent from rag_agent_pipeline.py: RAG retrieval as a tool, durable
short-term memory (SqliteSaver), persistent long-term memory across conversations
(SqliteStore), PII redaction, content moderation, and model-call resilience.

Conversation history is rendered straight from the LangGraph checkpointer's state —
not from an app-side list — so what you see on screen is proof of persistence, not a
UI illusion. Reload the page with the same thread_id and it's still there.

Every assistant turn also carries a full observability trace (tokens, latency, the
exact messages sent to the LLM, the retrieval pipeline's dense/sparse/fused/reranked
scores) riding along on the message objects themselves — see rag_agent_pipeline.py's
`capture_telemetry` middleware and `search_knowledge_base`'s tool artifact. That's why
the debug panels below work identically for a message from ten seconds ago and one
from a conversation you resumed after restarting the app.

Run with:
    streamlit run app.py
"""

import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).parent))
from rag_agent_pipeline import (
    Context, MEMORY_POLICY, build_agent, list_threads, record_thread, remember_fact,
)
import eval_pipeline

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MEMORY_DIR = Path(__file__).parent / "memory_store"
MEMORY_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Production RAG Chatbot + Memory", page_icon="🧠", layout="wide")

# ---- Look & feel ---------------------------------------------------------
# Palette matches the course's Marp deck theme (dark navy + sky accent). Citation
# colors are a small fixed cycle -- each source gets one color, used consistently for
# its inline [n] marker AND its evidence card's left edge, so "where did this sentence
# come from" is answerable at a glance instead of by cross-referencing numbers.
CITATION_COLORS = ["blue", "green", "orange", "violet", "red", "gray"]
COLOR_HEX = {
    "blue": "#3b82f6", "green": "#16a34a", "orange": "#f59e0b",
    "violet": "#8b5cf6", "red": "#ef4444", "gray": "#6b7280",
}

st.markdown(
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');"
    "[data-testid=\"stAppViewContainer\"], [data-testid=\"stSidebar\"] {"
    "  font-family: 'Inter', -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; }"
    "code, pre, kbd {"
    "  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace !important; }"
    "h1, h2, h3, h4 { letter-spacing: -0.01em; }"
    "[data-testid=\"stChatMessage\"] { border-radius: 14px; }"
    "[data-testid=\"stChatInput\"] textarea { border-radius: 12px; }"
    "button[kind=\"primary\"] { font-weight: 600; letter-spacing: 0.01em; }"
    + "".join(
        f'[class*="-clr-{color}"] {{ border-left: 3px solid {hexcode} !important; }}'
        for color, hexcode in COLOR_HEX.items()
    )
    + "</style>",
    unsafe_allow_html=True,
)

# ---- Session state -----------------------------------------------------
for key, default in [
    ("agent", None), ("store", None), ("stack", None), ("index", None), ("reranker", None),
    ("stats", None), ("doc_names", []), ("user_id", "demo-user"),
    ("thread_id", str(uuid.uuid4())[:8]),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.store is None:
    import sqlite3
    from contextlib import ExitStack
    from langgraph.store.sqlite import SqliteStore
    _stack = ExitStack()
    _store = _stack.enter_context(
        SqliteStore.from_conn_string(str(MEMORY_DIR / "long_term_memory.db"))
    )
    _store.setup()
    st.session_state.store = _store
    st.session_state.stack = _stack


# ---- Citation coloring + lightweight grounding check ---------------------
def colorize_citations(answer: str, n_sources: int) -> str:
    """Replace [n] markers with theme-colored badges, one fixed color per source
    number, reused for that source's evidence card so a marker and its origin are
    visually the same color -- not just cross-referenced by a shared digit."""
    def repl(m):
        n = int(m.group(1))
        if 1 <= n <= n_sources:
            color = CITATION_COLORS[(n - 1) % len(CITATION_COLORS)]
            return f":{color}-badge[{n}]"
        return m.group(0)
    return re.sub(r"\[(\d+)\]", repl, answer)


_WORD_RE = re.compile(r"[a-zA-Z]{4,}")


def _word_overlap(sentence: str, source_text: str) -> float | None:
    sent_words = {w.lower() for w in _WORD_RE.findall(sentence)}
    if not sent_words:
        return None
    source_words = {w.lower() for w in _WORD_RE.findall(source_text)}
    return len(sent_words & source_words) / len(sent_words)


def check_citation_grounding(answer: str, source_text_by_rank: dict) -> dict:
    """For every [n] marker, find the sentence it's attached to and measure how much
    of that sentence's vocabulary actually appears in source n's chunk. This is a
    cheap, explainable stand-in for RAGAS-style faithfulness scoring (see Notebook
    13's M06 lineage) -- not a replacement for it, but enough to flag a citation that
    looks like the model attached the wrong number rather than genuinely quoting it."""
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    results = {}
    for sent in sentences:
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", sent)}
        clean = re.sub(r"\[\d+\]", "", sent)
        for n in cited:
            src = source_text_by_rank.get(n)
            if not src:
                continue
            ratio = _word_overlap(clean, src)
            if ratio is None:
                continue
            if n not in results or ratio > results[n]:
                results[n] = ratio
    return results


def _confidence_label(ratio: float) -> tuple[str, str]:
    if ratio >= 0.6:
        return "✅", "strong match"
    if ratio >= 0.35:
        return "⚠️", "medium match"
    return "❗", "weak match — verify"


# ---- Per-turn detail panels ------------------------------------------------
def group_turns(messages: list) -> list[dict]:
    """Flatten the checkpointer's message list into per-question turns. A turn with a
    tool call produces TWO AIMessages (one deciding to call search_knowledge_base, one
    writing the final answer) -- both are kept so the UI can show "2 LLM calls this
    turn" instead of silently collapsing them into one."""
    turns = []
    current = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            current = {"human": msg, "ai_calls": [], "tool_msgs": []}
            turns.append(current)
        elif current is None:
            continue
        elif isinstance(msg, ToolMessage):
            current["tool_msgs"].append(msg)
        elif isinstance(msg, AIMessage):
            current["ai_calls"].append(msg)
    return turns


def render_sources_tab(answer: str, tool_msg: ToolMessage | None, artifact: dict | None, msg_key: str):
    if artifact is None:
        if tool_msg is not None:
            st.caption("This turn called search_knowledge_base, but predates the "
                       "evidence-trace instrumentation — no detail was recorded for it.")
        else:
            st.caption("No retrieval tool call on this turn — nothing to cite (e.g. the "
                       "question was about stored user facts, or was blocked upstream).")
        return

    if artifact.get("type") == "summary_sample":
        st.caption(
            f"Whole-document summary — sampled {len(artifact['sampled'])} of "
            f"{artifact['total_chunks']} total chunks evenly across the document "
            f"(no similarity search, no groundedness threshold — see the "
            f"Retrieval pipeline tab for why)."
        )
        source_text_by_rank = {r["rank"]: r["text"] for r in artifact["sampled"]}
        grounding = check_citation_grounding(answer, source_text_by_rank)
        for r in artifact["sampled"]:
            i = r["rank"]
            color = CITATION_COLORS[(i - 1) % len(CITATION_COLORS)]
            with st.container(border=True, key=f"src-{msg_key}-{i}-clr-{color}"):
                head_l, head_r = st.columns([4, 1])
                head_l.markdown(f":{color}-badge[{i}]  **{r['source']}**")
                head_r.markdown(f":gray-badge[p.{r['page']}]")
                st.caption(r["text"])
                if i in grounding:
                    icon, label = _confidence_label(grounding[i])
                    st.caption(f"{icon} Citation check: {label} between the cited "
                               f"sentence and this source ({grounding[i]:.0%} word overlap).")
                else:
                    st.caption("— Not cited inline by the model's answer this turn.")
        return

    if not artifact["grounded"]:
        st.warning(
            f"⚠️ Nothing cleared the groundedness threshold "
            f"(best score was below **{artifact['min_rerank_score']}**) — the model was "
            f"instructed to say so rather than guess."
        )
        return

    sent = artifact["reranked_all"][: artifact["top_n"]]
    source_text_by_rank = {r["rank"]: r["text"] for r in sent}
    grounding = check_citation_grounding(answer, source_text_by_rank)

    for r in sent:
        i = r["rank"]
        color = CITATION_COLORS[(i - 1) % len(CITATION_COLORS)]
        with st.container(border=True, key=f"src-{msg_key}-{i}-clr-{color}"):
            head_l, head_r = st.columns([4, 1])
            head_l.markdown(f":{color}-badge[{i}]  **{r['source']}**")
            head_r.markdown(f":gray-badge[p.{r['page']}]")
            st.caption(f"Cross-encoder score: `{r['score']:.3f}`")
            st.caption(r["text"])
            if i in grounding:
                icon, label = _confidence_label(grounding[i])
                st.caption(f"{icon} Citation check: {label} between the cited sentence "
                           f"and this source ({grounding[i]:.0%} word overlap).")
            else:
                st.caption("— Not cited inline by the model's answer this turn.")


def render_pipeline_tab(tool_msg: ToolMessage | None, artifact: dict | None):
    if artifact is None:
        if tool_msg is not None:
            st.caption("This turn called search_knowledge_base, but predates the "
                       "evidence-trace instrumentation — no detail was recorded for it.")
        else:
            st.caption("No retrieval happened this turn.")
        return

    if artifact.get("type") == "summary_sample":
        st.info(
            "This turn used **summarize_document**, not search_knowledge_base — no "
            "query embedding, no similarity search, no rerank scores apply. Instead, "
            "chunks were sampled evenly across the whole document in original order."
        )
        c1, c2 = st.columns(2)
        c1.metric("Total chunks in document", artifact["total_chunks"])
        c2.metric("Chunks sampled", len(artifact["sampled"]))
        st.caption(
            "Why not search_knowledge_base for 'summarize the paper'? Semantic search "
            "finds chunks that resemble the literal wording of the request — often a "
            "stray figure caption or appendix note — not the chunks that best "
            "represent the document as a whole."
        )
        return

    st.markdown(f"**Query embedded:** `{artifact['query']}`")
    c1, c2, c3 = st.columns(3)
    c1.metric("Embedding model", artifact["embedding_model"])
    c2.metric("Dimensions", artifact["embedding_dims"])
    c3.metric("Retrieval + rerank time", f"{artifact['elapsed_ms']} ms")

    with st.expander(
        f"🔢 What the query embedding actually looks like "
        f"(first 8 of {artifact['embedding_dims']} dims)"
    ):
        st.code(str(artifact["query_embedding_preview"]), language="python")
        st.caption("Every indexed chunk is the same kind of vector — retrieval is "
                   "comparing lists of numbers like this one, not reading text.")

    dense_tab, sparse_tab, fused_tab, rerank_tab = st.tabs(
        ["Dense (embeddings)", "Sparse (BM25)", "Fused (RRF)", "Reranked (cross-encoder)"]
    )

    def _rows(records, score_label):
        return [
            {
                "rank": r["rank"], "source": r["source"], "page": r["page"],
                score_label: r["score"],
                "preview": r["text"][:90] + ("…" if len(r["text"]) > 90 else ""),
            }
            for r in records
        ]

    with dense_tab:
        st.caption("Cosine similarity between the query embedding and each chunk's "
                   "embedding — meaning-based, no keyword overlap required.")
        st.dataframe(_rows(artifact["dense"], "cosine"), hide_index=True)
    with sparse_tab:
        st.caption("BM25 lexical score — exact term overlap, no meaning involved. "
                   "Catches exact codes/names dense search can miss.")
        st.dataframe(_rows(artifact["sparse"], "bm25"), hide_index=True)
    with fused_tab:
        st.caption("Reciprocal Rank Fusion merges both rankings above into one "
                   "candidate list — a chunk that ranks well on either signal rises.")
        st.dataframe(_rows(artifact["fused"], "rrf"), hide_index=True)
    with rerank_tab:
        st.caption(
            f"Cross-encoder re-scores every fused candidate jointly with the query "
            f"(slower, more accurate). Only the top {artifact['top_n']} are sent to the "
            f"LLM, and only if the best one clears the groundedness threshold "
            f"(**{artifact['min_rerank_score']}**)."
        )
        for r in artifact["reranked_all"]:
            sent_to_llm = artifact["grounded"] and r["rank"] <= artifact["top_n"]
            icon = "✅ sent to LLM" if sent_to_llm else "— not sent"
            st.markdown(f"**#{r['rank']}** {r['source']} (p.{r['page']}) — "
                       f"score `{r['score']:.3f}` — {icon}")


def render_tokens_tab(ai_calls: list, client_timing: dict | None):
    calls = [m for m in ai_calls if m.response_metadata.get("telemetry")]
    if not calls:
        st.caption("No telemetry recorded for this turn (message predates this "
                   "instrumentation being added).")
        return

    total_in = sum((m.response_metadata["telemetry"]["usage"] or {}).get("input_tokens", 0) for m in calls)
    total_out = sum((m.response_metadata["telemetry"]["usage"] or {}).get("output_tokens", 0) for m in calls)
    total_cost = sum(m.response_metadata["telemetry"].get("estimated_cost_usd", 0) or 0 for m in calls)
    server_latency = sum(m.response_metadata["telemetry"]["latency_s"] for m in calls)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LLM calls this turn", len(calls))
    c2.metric("Input tokens", total_in)
    c3.metric("Output tokens", total_out)
    c4.metric("Total tokens", total_in + total_out)

    c5, c6, c7 = st.columns(3)
    c5.metric("Estimated cost", f"${total_cost:.5f}")
    if client_timing:
        c6.metric("Total latency", f"{client_timing['total_latency']:.2f}s")
        ttft = client_timing.get("ttft")
        c7.metric("Time to first token", f"{ttft:.2f}s" if ttft is not None else "n/a — no stream")
    else:
        c6.metric("Model latency (server-side)", f"{server_latency:.2f}s")
        c7.metric("Time to first token", "live turns only")

    st.caption("Cost is illustrative — based on constants in rag_agent_pipeline.py, "
               "not a live lookup of OpenAI's current published rates.")

    with st.expander(f"Per-call breakdown ({len(calls)} call{'s' if len(calls) != 1 else ''})"):
        for i, m in enumerate(calls):
            t = m.response_metadata["telemetry"]
            usage = t["usage"] or {}
            kind = "tool-selection call" if t["had_tool_calls"] else "final answer call"
            st.markdown(
                f"**Call {i + 1} — {kind}**\n"
                f"- Messages sent: {t['messages_sent']} (of {t['messages_in_full_history']} stored)\n"
                f"- Tokens: {usage.get('input_tokens', '–')} in / "
                f"{usage.get('output_tokens', '–')} out / {usage.get('total_tokens', '–')} total\n"
                f"- Server latency: {t['latency_s']}s"
            )


def render_memory_tab(ai_calls: list):
    calls = [m for m in ai_calls if m.response_metadata.get("telemetry")]
    if not calls:
        st.caption("No telemetry recorded for this turn.")
        return
    t = calls[-1].response_metadata["telemetry"]
    policy = t["memory_policy"]

    st.markdown(
        f"**Active policy:** summarize once the conversation exceeds "
        f"**{policy['trigger_tokens']} tokens**, keeping the last "
        f"**{policy['keep_messages']} messages** verbatim."
    )
    if t["summarized_this_turn"]:
        st.warning(
            f"🗜️ Summarization fired this turn — {t['messages_in_full_history']} stored "
            f"messages were condensed down to {t['messages_sent']} sent to the model."
        )
    else:
        st.caption(
            f"Below the threshold — all {t['messages_sent']} of "
            f"{t['messages_in_full_history']} stored messages were sent as-is."
        )

    with st.expander(f"📨 Exact messages sent to the LLM this call ({t['messages_sent']})"):
        for m in t["messages_preview"]:
            st.markdown(f"**{m['role']}:** {m['content']}")

    with st.expander("🧾 System prompt actually sent"):
        st.code(t["system_prompt"] or "(none)", language="markdown")


def render_turn_detail(final_ai: AIMessage, tool_msg: ToolMessage | None,
                        ai_calls: list, msg_key: str):
    # Client-side wall-clock timing (total latency, time-to-first-token) is measured
    # in the chat-input handler below, around the streaming call -- it can't ride on
    # response_metadata like the server-side telemetry does, because by the time
    # .stream() returns, the checkpointer has already written the un-mutated message.
    # Session-scoped (not disk-persisted) so it survives the st.rerun() that follows
    # every turn, but is honestly absent after a real page reload -- see the "n/a"
    # fallback in render_tokens_tab.
    client_timing = st.session_state.get("client_timing", {}).get(final_ai.id)
    artifact = tool_msg.artifact if (tool_msg is not None and isinstance(tool_msg.artifact, dict)) else None
    n_sources = 0
    if artifact and artifact.get("type") == "summary_sample":
        n_sources = len(artifact["sampled"])
    elif artifact and artifact.get("grounded"):
        n_sources = min(len(artifact["reranked_all"]), artifact["top_n"])

    st.markdown(colorize_citations(final_ai.content, n_sources) if n_sources else final_ai.content)

    tabs = st.tabs(["📚 Sources", "🔍 Retrieval pipeline", "📊 Tokens & latency", "🧠 Memory & context"])
    with tabs[0]:
        render_sources_tab(final_ai.content, tool_msg, artifact, msg_key)
    with tabs[1]:
        render_pipeline_tab(tool_msg, artifact)
    with tabs[2]:
        render_tokens_tab(ai_calls, client_timing)
    with tabs[3]:
        render_memory_tab(ai_calls)


# ---- Evaluation tab ---------------------------------------------------------
def _fmt_pct(v):
    return f"{v:.0%}" if v is not None else "—"


def _fmt_score(v):
    return f"{v:.3f}" if v is not None else "—"


def _fmt_delta_pct(v):
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{v:.0%}"


def _fmt_delta_score(v):
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{v:.3f}"


def render_eval_result(result: dict):
    """Shared rendering for both a just-finished run and a saved run pulled from
    history -- same dict shape either way. Organized as four distinct report
    cards -- retrieval, reranking, generation, chunking -- each answering its own
    question directly, rather than one blended pile of numbers."""
    r = result["retrieval"]
    ro, ar, lift = r["retrieval_only"], r["after_rerank"], r["reranking_lift"]
    st.markdown(
        f"**{result['test_set_size']} question(s)** generated from the indexed "
        f"chunks · run took **{result['elapsed_s']}s**"
    )

    # ---- 1. Retrieval quality: dense + BM25 fusion, in isolation -----------
    st.markdown("##### 🔍 Retrieval quality — fusion alone, before reranking touches anything")
    st.caption("Where the correct chunk lands right after dense+BM25 RRF fusion.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Recall@1", _fmt_pct(ro["recall_at_1"]))
    c2.metric("Recall@3", _fmt_pct(ro["recall_at_3"]))
    c3.metric("Recall@10", _fmt_pct(ro["recall_at_10"]))
    c4.metric("NDCG@10", _fmt_score(ro["ndcg_at_10"]))
    c5.metric("MRR", _fmt_score(ro["mrr"]))

    # ---- 2. Reranking quality: the cross-encoder's marginal contribution ---
    st.markdown("##### 🎯 Reranking quality — cross-encoder lift over fusion alone")
    st.caption(
        "Same candidate pool both times (reranking only reorders it, never adds or "
        "drops candidates) -- these deltas isolate what the cross-encoder itself "
        "contributed. Positive = reranking helped; negative = it made things worse "
        "for this document."
    )
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("ΔRecall@1", _fmt_delta_pct(lift.get("recall_at_1")))
    d2.metric("ΔRecall@3", _fmt_delta_pct(lift.get("recall_at_3")))
    d3.metric("ΔRecall@10", _fmt_delta_pct(lift.get("recall_at_10")))
    d4.metric("ΔNDCG@10", _fmt_delta_score(lift.get("ndcg_at_10")))
    d5.metric("ΔMRR", _fmt_delta_score(lift.get("mrr")))
    with st.expander("Final ranking (after reranking) — full numbers"):
        e1, e2, e3, e4, e5 = st.columns(5)
        e1.metric("Recall@1", _fmt_pct(ar["recall_at_1"]))
        e2.metric("Recall@3", _fmt_pct(ar["recall_at_3"]))
        e3.metric("Recall@10", _fmt_pct(ar["recall_at_10"]))
        e4.metric("NDCG@10", _fmt_score(ar["ndcg_at_10"]))
        e5.metric("MRR", _fmt_score(ar["mrr"]))
        f1, f2, f3 = st.columns(3)
        f1.metric("MCC@1", _fmt_score(ar["mcc_at_1"]))
        f2.metric("MCC@3", _fmt_score(ar["mcc_at_3"]))
        f3.metric("MCC@10", _fmt_score(ar["mcc_at_10"]))
        st.caption(
            "MCC is a binary-classification metric, not a ranking one -- included "
            "because it was asked for, but with severe class imbalance here (one "
            "relevant chunk per question against the whole candidate pool), treat "
            "it as a secondary signal alongside Recall@K/NDCG/MRR, not a standalone "
            "verdict. '—' means undefined for this run."
        )

    # ---- 3. Generation quality: RAGAS + DeepEval, blended into one verdict -
    st.markdown("##### ✍️ Generation quality — is the LLM answering well from what it retrieved?")
    gen_scores = []
    for name, key in [("RAGAS", "ragas"), ("DeepEval", "deepeval")]:
        section = result.get(key)
        st.markdown(f"**{name}**")
        if section is None:
            st.caption("Not run for this evaluation.")
            continue
        if "error" in section:
            st.error(f"{name} failed: {section['error']}")
            continue
        metric_keys = [k for k in section if k not in ("n_scored", "n_total", "per_question")]
        cols = st.columns(len(metric_keys))
        for col, mk in zip(cols, metric_keys):
            scored = section.get("n_scored", {}).get(mk)
            total = section.get("n_total")
            label = mk.replace("_", " ").title()
            if scored is not None and total is not None and scored < total:
                label += f" ({scored}/{total})"
            col.metric(label, _fmt_score(section[mk]))
            if section[mk] is not None:
                gen_scores.append(section[mk])
    if gen_scores:
        overall = sum(gen_scores) / len(gen_scores)
        verdict = "strong" if overall >= 0.85 else "solid" if overall >= 0.65 else "needs attention"
        st.info(
            f"**Overall generation score: {overall:.3f}** (plain mean across every "
            f"RAGAS + DeepEval metric scored above) — {verdict}."
        )

    # ---- 4. Chunking quality: inherently a cross-run comparison ------------
    st.markdown("##### ✂️ Chunking quality")
    strategy_label = (
        "Semantic (topic-based)" if result["config"].get("chunking_strategy") == "semantic" else "Fixed-size"
    )
    st.caption(
        f"This run's knowledge base used **{strategy_label}** chunking. Chunking has "
        f"no direct score of its own -- its only effect on every number above is "
        f"indirect, through what content ends up retrievable at all. The honest way "
        f"to measure it: rebuild this same document with the other chunking strategy, "
        f"run evaluation again, and compare the **Retrieval quality** numbers between "
        f"the two runs side by side in **Compare runs** below — same document, same "
        f"question style, only the chunk boundaries differ."
    )

    with st.expander("Per-question detail"):
        rows = []
        retrieval_by_q = {pq["question"]: pq for pq in r["per_question"]}
        ragas_by_q = {pq["question"]: pq for pq in (result.get("ragas") or {}).get("per_question", [])}
        deepeval_by_q = {pq["question"]: pq for pq in (result.get("deepeval") or {}).get("per_question", [])}
        for q, rq in retrieval_by_q.items():
            row = {
                "question": q[:80],
                "fused_rank": rq["fused_rank"], "rerank_rank": rq["rerank_rank"],
                "pool_size": rq["pool_size"],
            }
            if q in ragas_by_q:
                row["ragas_faithfulness"] = ragas_by_q[q].get("faithfulness")
            if q in deepeval_by_q:
                row["deepeval_faithfulness"] = deepeval_by_q[q].get("faithfulness")
            rows.append(row)
        st.dataframe(rows, hide_index=True)


def render_evaluation_tab():
    st.markdown("### 🧪 Retrieval & generation evaluation")
    st.caption(
        "Generates test questions from the chunks actually indexed in this knowledge "
        "base -- each chunk is its own question's ground truth -- then runs them "
        "through the real retrieval pipeline (Recall@K, NDCG, MCC) and the real "
        "generation pipeline (RAGAS, DeepEval). Not automatic on every build: a full "
        "run is dozens to hundreds of LLM calls, so it's a deliberate action here, "
        "not a hidden tax on the fast iteration loop."
    )

    total_chunks = len(st.session_state.index.chunks) if st.session_state.index else 0
    with st.container(border=True):
        c1, c2 = st.columns(2)
        questions_per_chunk = c1.slider("Questions per chunk", 1, 3, 2)
        max_chunks = c2.slider(
            "Chunks sampled", 1, max(1, total_chunks), min(15, max(1, total_chunks)),
            help="Sampled evenly across the whole document, not just the first N chunks.",
        )
        c3, c4 = st.columns(2)
        run_ragas = c3.checkbox("Score with RAGAS", value=True)
        run_deepeval = c4.checkbox("Score with DeepEval", value=True)

        est_q = questions_per_chunk * min(max_chunks, total_chunks)
        est_calls = est_q * (2 + (4 if run_ragas else 0) + (4 if run_deepeval else 0))
        st.caption(f"Estimated ~{est_q} question(s), ~{est_calls} LLM call(s) — can take a few minutes.")

        run_clicked = st.button(
            "▶️ Run evaluation", type="primary", use_container_width=True,
            disabled=total_chunks == 0,
        )

    if run_clicked:
        with st.status("Running evaluation…", expanded=True) as status:
            def on_progress(msg, _status=status):
                _status.write(msg)
            try:
                s = st.session_state.stats
                result = eval_pipeline.run_evaluation(
                    index=st.session_state.index, reranker=st.session_state.reranker,
                    chunks=st.session_state.index.chunks,
                    top_k=s["top_k"], top_n=s["top_n"], min_rerank_score=s["min_rerank_score"],
                    chunking_strategy=s.get("chunking_strategy", "fixed"),
                    questions_per_chunk=questions_per_chunk, max_chunks=max_chunks,
                    run_ragas=run_ragas, run_deepeval=run_deepeval, on_progress=on_progress,
                )
            except Exception as exc:
                status.update(label=f"Evaluation failed: {exc}", state="error")
                st.session_state["last_eval_result"] = None
            else:
                run_id = eval_pipeline.save_eval_run(st.session_state.store, st.session_state.user_id, result)
                status.update(
                    label=f"Evaluation complete — {result['test_set_size']} question(s), "
                          f"{result['elapsed_s']}s",
                    state="complete",
                )
                st.session_state["last_eval_result"] = result
                st.toast(f"Saved as run {run_id}", icon="✅")

    if st.session_state.get("last_eval_result"):
        st.divider()
        st.markdown("#### Latest run")
        render_eval_result(st.session_state["last_eval_result"])

    st.divider()
    st.markdown("#### 📈 Compare runs")
    st.caption(
        "This is the actual answer to 'how good is chunking': run evaluation once per "
        "chunking strategy on the same document and read the Retrieval columns below "
        "side by side."
    )
    runs = eval_pipeline.list_eval_runs(st.session_state.store, st.session_state.user_id)
    if not runs:
        st.caption("No saved evaluation runs yet for this user.")
        return

    comparison_rows = []
    for item in runs:
        v = item.value
        after = v["retrieval"]["after_rerank"]
        lift = v["retrieval"]["reranking_lift"]
        comparison_rows.append({
            "label": v.get("label"), "chunking": v.get("config", {}).get("chunking_strategy"),
            "when": v.get("created_at", "")[:19].replace("T", " "), "questions": v.get("test_set_size"),
            "R@1": after["recall_at_1"], "R@3": after["recall_at_3"], "R@10": after["recall_at_10"],
            "NDCG@10": after["ndcg_at_10"], "MRR": after["mrr"], "MCC@10": after["mcc_at_10"],
            "Rerank ΔRecall@1": lift.get("recall_at_1"),
            "RAGAS Faithfulness": (v.get("ragas") or {}).get("faithfulness"),
            "DeepEval Faithfulness": (v.get("deepeval") or {}).get("faithfulness"),
        })
    st.dataframe(comparison_rows, hide_index=True)

    with st.expander(f"Full detail per run ({len(runs)})"):
        for item in runs:
            v = item.value
            st.markdown(f"**{v.get('label')}** — {v.get('created_at', '')[:19].replace('T', ' ')}")
            render_eval_result(v)
            if st.button("🗑️ Delete this run", key=f"del-eval-{item.key}"):
                eval_pipeline.delete_eval_run(st.session_state.store, st.session_state.user_id, item.key)
                st.rerun()
            st.divider()


# ---- Sidebar: knowledge base + identity/memory --------------------------
with st.sidebar:
    st.markdown("## 🧠 RAG Studio")
    st.caption("Upload documents, tune retrieval, and manage who the assistant remembers.")

    with st.container(border=True):
        st.markdown("#### 📚 Knowledge base")
        uploaded_files = st.file_uploader(
            "Upload document(s)", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True,
        )
        if not uploaded_files:
            st.caption("PDF, Word, text, or Markdown — one or more files.")

        with st.expander("Retrieval tuning", icon="⚙️"):
            chunking_strategy = st.radio(
                "Chunking strategy",
                options=["fixed", "semantic"],
                format_func=lambda v: "Fixed-size (current default)" if v == "fixed" else "Semantic (topic-based)",
                help="Fixed-size splits every N characters regardless of content — "
                     "simple, fast, and can slice a single idea in half by coincidence "
                     "of length. Semantic embeds sentences and only starts a new chunk "
                     "where the topic actually shifts — usually better retrieval, but "
                     "slower and costs extra embedding calls to build.",
            )
            if chunking_strategy == "fixed":
                chunk_size = st.slider("Chunk size (characters)", 200, 1500, 500, step=50)
                chunk_overlap = st.slider("Chunk overlap", 0, 300, 80, step=10)
                semantic_breakpoint_percentile = 90
            else:
                chunk_size, chunk_overlap = 500, 80
                semantic_breakpoint_percentile = st.slider(
                    "Breakpoint sensitivity (percentile)", 70, 99, 90,
                    help="Lower = more, smaller chunks (splits on smaller topic shifts). "
                         "Higher = fewer, larger chunks (only splits on big shifts).",
                )
            top_k = st.slider("Candidates after fusion (top-k)", 4, 20, 8)
            top_n = st.slider("Chunks sent to the LLM after rerank (top-n)", 1, 8, 4)
            min_rerank_score = st.slider(
                "Groundedness threshold (min rerank score)", -12.0, 5.0, -9.5, step=0.5,
            )

        build_clicked = st.button("🔨 Build knowledge base", type="primary", use_container_width=True)

        if st.session_state.stats is not None:
            s = st.session_state.stats
            st.divider()
            st.markdown("**🗄️ Vector DB & index**")
            strategy_label = "Semantic" if s.get("chunking_strategy") == "semantic" else "Fixed-size"
            st.caption(
                f"Dense: {s['vector_db']} · `{s['embedding_model']}` ({s['embedding_dims']}-dim)  \n"
                f"Sparse: {s['sparse_index']}  \n"
                f"Chunking: {strategy_label}  \n"
                f"{s['chunks']} chunks indexed from {s['pages']} page(s), {s['files']} file(s)"
            )

    with st.container(border=True):
        st.markdown("#### 🪪 Identity & memory")
        new_user_id = st.text_input("User ID (owns long-term memory)", value=st.session_state.user_id)
        if new_user_id != st.session_state.user_id:
            st.session_state.user_id = new_user_id

        st.caption(f"Conversation: `{st.session_state.thread_id}`")
        st.caption(
            f"Summarization policy: triggers at {MEMORY_POLICY['trigger_tokens']} tokens, "
            f"keeps last {MEMORY_POLICY['keep_messages']} messages"
        )
        if st.button("🆕 New conversation, same user", use_container_width=True,
                      help="Resets short-term chat history. Long-term facts about this user "
                           "still carry over — that's the whole point of the split."):
            st.session_state.thread_id = str(uuid.uuid4())[:8]
            st.rerun()

        if st.session_state.store is not None:
            st.markdown("**Previous conversations**")
            threads = list_threads(st.session_state.store, st.session_state.user_id)
            if threads:
                with st.container(height=160):
                    for t in threads:
                        is_current = t.key == st.session_state.thread_id
                        label = f"{'▶ ' if is_current else ''}{t.value['preview']}"
                        if st.button(label, key=f"thread_{t.key}", use_container_width=True,
                                     disabled=is_current):
                            st.session_state.thread_id = t.key
                            st.rerun()
            else:
                st.caption("_No conversations yet — send a message to start one._")

            st.markdown("**Long-term facts**")
            memories = st.session_state.store.search(("memories", st.session_state.user_id))
            if memories:
                with st.container(height=120):
                    for m in memories:
                        st.caption(f"• {m.value['text']}")
            else:
                st.caption("_Nothing stored for this user yet._")

            with st.form("remember_fact_form", clear_on_submit=True):
                fact_text = st.text_input("Teach it a fact about this user")
                if st.form_submit_button("💾 Remember") and fact_text.strip():
                    remember_fact(st.session_state.store, st.session_state.user_id,
                                   str(uuid.uuid4())[:8], fact_text.strip())
                    st.rerun()

# ---- Build / rebuild the agent -----------------------------------------
if build_clicked:
    if not uploaded_files:
        st.sidebar.error("Upload at least one file first.")
    else:
        with st.status("Building knowledge base…", expanded=True) as build_status:
            st.write(f"Parsing {len(uploaded_files)} file(s)…")
            tmp_dir = Path(tempfile.mkdtemp())
            saved_paths = []
            for f in uploaded_files:
                dest = tmp_dir / f.name
                dest.write_bytes(f.getvalue())
                saved_paths.append(str(dest))

            strategy_note = "semantic (topic-based)" if chunking_strategy == "semantic" else "fixed-size"
            st.write(f"Chunking ({strategy_note}), embedding, and indexing (dense + BM25)…")
            db_dir = Path(__file__).parent / "memory_store"
            agent, store, stack, stats, index, reranker = build_agent(
                saved_paths, db_dir=str(db_dir),
                chunking_strategy=chunking_strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                semantic_breakpoint_percentile=semantic_breakpoint_percentile,
                top_k=top_k, top_n=top_n, min_rerank_score=min_rerank_score,
                existing_store=st.session_state.store,
            )

            st.session_state.agent = agent
            st.session_state.store = store
            st.session_state.stack = stack
            st.session_state.index = index
            st.session_state.reranker = reranker
            st.session_state.stats = stats
            st.session_state.doc_names = [f.name for f in uploaded_files]
            st.session_state.thread_id = str(uuid.uuid4())[:8]

            build_status.update(
                label=f"Knowledge base ready — {stats['pages']} page(s), {stats['chunks']} chunks",
                state="complete",
            )

        st.toast(f"Ready — **{', '.join(st.session_state.doc_names)}**", icon="✅")
        st.rerun()

# ---- Main -----------------------------------------------------------------
st.title("🧠 Production RAG Chatbot + Memory")
st.caption(
    "RAG (hybrid retrieval → rerank → cited, grounded answers) as an agent tool, wrapped "
    "with durable short-term memory, persistent long-term memory, PII redaction, content "
    "moderation, and model-call resilience — everything from Notebook 11, applied to the "
    "Notebook 13 RAG engine. Every turn below carries a full observability trace: tokens, "
    "latency, the exact context sent to the LLM, and the retrieval pipeline's scores at "
    "every stage."
)

if st.session_state.agent is None:
    with st.container(border=True):
        st.markdown("### 📥 No knowledge base yet")
        st.write(
            "Upload a PDF, Word, text, or Markdown file in the sidebar, then click "
            "**Build knowledge base** to start asking grounded, cited questions."
        )
    st.stop()

doc_list = ", ".join(st.session_state.doc_names) or "unknown"
st.markdown(
    f":primary-badge[📄 {doc_list}]  :gray-badge[🪪 {st.session_state.user_id}]  "
    f":gray-badge[💬 {st.session_state.thread_id}]"
)

config = {"configurable": {"thread_id": st.session_state.thread_id}}
context = Context(user_id=st.session_state.user_id)


def render_history():
    """Render straight from the checkpointer's persisted state -- not an app-side
    list. Every panel below (tokens, retrieval trace, memory) reads from the same
    message objects, so a reloaded page shows identical detail to the live turn."""
    state = st.session_state.agent.get_state(config)
    messages = state.values.get("messages", []) if state.values else []

    for i, turn in enumerate(group_turns(messages)):
        with st.chat_message("user", avatar="🧑"):
            st.markdown(turn["human"].content)

        final_ai = next((m for m in reversed(turn["ai_calls"]) if m.content), None)
        if final_ai is None:
            continue
        tool_msg = turn["tool_msgs"][-1] if turn["tool_msgs"] else None
        with st.chat_message("assistant", avatar="🧠"):
            render_turn_detail(final_ai, tool_msg, turn["ai_calls"], msg_key=f"hist-{i}")


chat_tab, eval_tab = st.tabs(["💬 Chat", "🧪 Evaluation"])

with chat_tab:
    render_history()

    question = st.chat_input(f"Ask something about {doc_list}...")
    if question:
        record_thread(st.session_state.store, st.session_state.user_id, st.session_state.thread_id, question)

        with st.chat_message("user", avatar="🧑"):
            st.markdown(question)

        with st.chat_message("assistant", avatar="🧠"):
            placeholder = st.empty()
            t0 = time.perf_counter()
            ttft = None
            streamed_text = ""
            try:
                for chunk, _meta in st.session_state.agent.stream(
                    {"messages": question}, config, context=context, stream_mode="messages",
                ):
                    if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str) and chunk.content:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        streamed_text += chunk.content
                        placeholder.markdown(streamed_text + "▌")
            except Exception:
                streamed_text = ""

            total_latency = time.perf_counter() - t0

            if not streamed_text:
                # Streaming produced no incremental content (provider/middleware combo
                # didn't support it this turn) -- fall back to a plain blocking call so
                # the user still gets an answer. Time-to-first-token isn't meaningful here.
                t0 = time.perf_counter()
                st.session_state.agent.invoke({"messages": question}, config, context=context)
                total_latency = time.perf_counter() - t0
                ttft = None

            placeholder.empty()
            state = st.session_state.agent.get_state(config)
            last_turn = group_turns(state.values.get("messages", []))[-1]
            final_ai = next((m for m in reversed(last_turn["ai_calls"]) if m.content), None)
            tool_msg = last_turn["tool_msgs"][-1] if last_turn["tool_msgs"] else None
            if final_ai is not None:
                if final_ai.id:
                    st.session_state.setdefault("client_timing", {})[final_ai.id] = {
                        "total_latency": total_latency, "ttft": ttft,
                    }
                render_turn_detail(final_ai, tool_msg, last_turn["ai_calls"], msg_key="live")
        st.rerun()

with eval_tab:
    render_evaluation_tab()
