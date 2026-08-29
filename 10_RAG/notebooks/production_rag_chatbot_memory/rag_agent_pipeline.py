"""
Production RAG chatbot with production-grade memory and guardrails.

Combines two things this course already built and validated separately:
  - Notebook 13's RAG engine: hybrid retrieval (dense + BM25, RRF-fused), cross-encoder
    rerank, grounded citations, groundedness guardrail (rag_pipeline.py).
  - Notebook 11's production chatbot patterns: durable checkpointing, token-budget
    summarization, persistent cross-session long-term memory, PII redaction, content
    moderation, and model-call resilience -- via LangGraph's create_agent + middleware.

The RAG retrieval becomes a TOOL the agent calls. The groundedness guardrail lives inside
that tool: if nothing relevant is found, the tool honestly says so, and the system prompt
instructs the agent to report that rather than guess -- the same "refuse over hallucinate"
contract as Notebook 13, expressed as agent instructions instead of a hard-coded branch.

Long-term memory here uses SqliteStore WITHOUT vector indexing. The indexed variant needs
a SQLite build with loadable-extension support, which not every Python distribution has
(the standard python.org / Homebrew macOS builds often don't). Without it, `store.search()`
returns every fact for a user unranked instead of the top-k most relevant -- for the handful
of facts a demo user accumulates, that's a fine trade for portability. A real deployment
would swap in a vector-capable store (Postgres + pgvector, or a SQLite build with extension
loading) purely by changing this one construction call.
"""

import sqlite3
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    PIIMiddleware,
    SummarizationMiddleware,
    dynamic_prompt,
    wrap_model_call,
)
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

# The RAG engine itself is NOT reimplemented here -- it's imported from the sibling
# production_rag_chatbot/ project, so both capstones share one retrieval implementation.
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "production_rag_chatbot"))
from rag_pipeline import (  # noqa: E402
    HybridIndex, Reranker, chunk_documents, format_sources, load_document,
)
try:
    from rag_pipeline import semantic_chunk_documents  # noqa: E402
except ImportError:
    # Notebook 13 pipeline is character-chunk only; memory app can fall back.
    semantic_chunk_documents = chunk_documents

MODEL = "gpt-4o-mini"
FALLBACK_MODEL = "openai:gpt-4o-mini"
MIN_RERANK_SCORE = -9.5

# Single source of truth for the summarization policy -- both the middleware below
# and the UI's "Memory" panel read these constants, so the app can never claim a
# policy it isn't actually running.
MEMORY_POLICY = {"trigger_tokens": 2000, "keep_messages": 10}

# Illustrative only -- OpenAI's published per-token rates change over time. Update
# these two numbers if you want the cost estimate in the UI to stay accurate.
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.00060

RAG_SYSTEM_PROMPT = """You are a strictly grounded assistant. You have exactly two permitted knowledge sources:

SOURCE 1 — UPLOADED DOCUMENTS
Two tools are available. Pick the right one for the question:
- search_knowledge_base(query): for specific questions ("what score did X get", "who wrote Y", "what does section 3 say about Z"). Finds the chunks most semantically similar to the question.
- summarize_document(): for broad requests — "summarize the paper", "what is this document about", "give me an overview". Semantic search over a single query is the WRONG tool for "the whole document": it only finds chunks that resemble the literal wording of the request (e.g. the words "summarize" or "overview"), which are often unrelated appendix or figure-caption fragments, not representative content.
Rules:
- Always call exactly one of these two tools before answering any document question.
- Answer ONLY using what the tool returns. Cite sources inline like [1], [2].
- If the tool returns no relevant information, respond with:
  "I could not find information about that in the uploaded documents."
- If the tool DID return content, you must use it. Never claim information is missing
  just because the returned chunks don't cover every possible aspect of a broad
  request — synthesize the best answer you can from what was actually retrieved.
- NEVER use your general training knowledge to answer, supplement, or fill gaps — even if you know the answer.

SOURCE 2 — USER MEMORY FACTS
Facts explicitly stored about this user appear below under "Known facts about this user".
Rules:
- Answer questions about the user ONLY from those stored facts.
- Do NOT call search_knowledge_base for user-related questions.
- If no relevant fact is stored, respond with:
  "I don't have that information stored for this user."
- NEVER infer, guess, or use general knowledge to answer user questions.

ABSOLUTE RULE: If neither source contains the answer, say so plainly. Never answer from general knowledge under any circumstances. Your only job is to retrieve and present — not to reason beyond what is explicitly provided."""


@dataclass
class Context:
    """Per-invocation context: which user is talking, for long-term memory lookup."""
    user_id: str


def make_search_tool(index: HybridIndex, reranker: Reranker, top_k=8, top_n=4,
                      min_rerank_score=MIN_RERANK_SCORE):
    """Wrap the hybrid-retrieval engine as an agent tool. The groundedness guardrail
    lives here: below the threshold, the tool reports nothing found instead of forcing
    the agent to answer from weak or irrelevant context.

    Uses `response_format="content_and_artifact"` so the tool can return two different
    things at once: `content` is the citation text the LLM actually reads and cites
    from (unchanged from before), and `artifact` is a rich debug trace -- dense-only
    ranking, sparse-only ranking, RRF fusion, and every reranked candidate's score --
    that never reaches the LLM's context window but rides along on the ToolMessage and
    gets checkpointed with it. That's what lets the UI show the full retrieval pipeline
    for a past turn without re-running retrieval or bloating the prompt.
    """

    @tool(
        description=(
            "Search the uploaded document(s) for information relevant to the query. "
            "MUST be called before answering any question about the documents. "
            "If this tool returns no relevant information, do not answer from general knowledge — "
            "report that the information was not found in the documents."
        ),
        response_format="content_and_artifact",
    )
    def search_knowledge_base(query: str):
        t0 = time.perf_counter()
        debug = index.search_debug(query, k=top_k)
        reranked_all = reranker.rerank_all(query, debug["fused_chunks"])
        reranked_top = reranked_all[:top_n]
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        grounded = bool(reranked_top and reranked_top[0][1] >= min_rerank_score)
        content = format_sources(reranked_top) if grounded else (
            "No relevant information found in the uploaded documents for this query."
        )

        artifact = {
            "type": "search",
            "query": query,
            "embedding_model": debug["embedding_model"],
            "embedding_dims": debug["embedding_dims"],
            "query_embedding_preview": debug["query_embedding_preview"],
            "dense": debug["dense"],
            "sparse": debug["sparse"],
            "fused": debug["fused"],
            "reranked_all": [
                {
                    "rank": i + 1, "source": c["source"], "page": c["page"],
                    "score": round(s, 4), "text": c["text"], "passed": s >= min_rerank_score,
                }
                for i, (c, s) in enumerate(reranked_all)
            ],
            "top_n": top_n,
            "min_rerank_score": min_rerank_score,
            "grounded": grounded,
            "elapsed_ms": elapsed_ms,
        }
        return content, artifact

    return search_knowledge_base


def make_summarize_tool(index: HybridIndex, max_chunks: int = 12):
    """A second retrieval tool for whole-document requests. search_knowledge_base
    does similarity search against ONE query embedding -- for "summarize the paper"
    that query embedding is closest to whatever chunks happen to contain words like
    "summary" or "overview" (often a stray figure caption or appendix note), not to
    the chunks that best represent the document as a whole. This tool skips
    similarity search entirely and instead samples chunks evenly across the full
    document in original order, so the model sees a representative cross-section
    instead of a query-shaped sliver of it.
    """

    @tool(
        description=(
            "Get a representative, evenly-sampled cross-section of the ENTIRE uploaded "
            "document, in original order. Use this INSTEAD OF search_knowledge_base "
            "whenever the user asks for a summary, overview, or general 'what is this "
            "document about' -- search_knowledge_base only finds chunks that resemble "
            "the literal wording of the request, which is the wrong tool for covering "
            "a whole document."
        ),
        response_format="content_and_artifact",
    )
    def summarize_document():
        chunks = index.chunks
        total = len(chunks)
        if total == 0:
            return "The knowledge base is empty.", {"type": "summary_sample", "total_chunks": 0, "sampled": []}

        n = min(max_chunks, total)
        step = max(1, total // n)
        sampled = chunks[::step][:n]

        content = "\n\n".join(
            f"[{i + 1}] ({c['source']}, p.{c['page']}) {c['text']}"
            for i, c in enumerate(sampled)
        )
        artifact = {
            "type": "summary_sample",
            "total_chunks": total,
            "sampled": [
                {"rank": i + 1, "source": c["source"], "page": c["page"], "text": c["text"]}
                for i, c in enumerate(sampled)
            ],
        }
        return content, artifact

    return summarize_document


@dynamic_prompt
def personalized_prompt(request) -> str:
    """Inject known long-term facts about this user into the system prompt, read from
    the persistent Store (keyed by user_id) rather than the checkpointer (keyed by
    thread_id) -- this is what lets the agent 'remember you' in a conversation it has
    never seen before."""
    user_id = request.runtime.context.user_id
    memories = request.runtime.store.search(("memories", user_id))
    facts = "\n".join(m.value["text"] for m in memories)
    base = RAG_SYSTEM_PROMPT
    if facts:
        base += f"\n\nKnown facts about this user:\n{facts}"
        print(f"[personalized_prompt] Injecting {len(memories)} fact(s) for user '{user_id}':\n{facts}")
    else:
        print(f"[personalized_prompt] No facts found for user '{user_id}'")
    return base


_moderation_client = None


def _get_moderation_client():
    global _moderation_client
    if _moderation_client is None:
        _moderation_client = OpenAI()
    return _moderation_client


@wrap_model_call
def moderate_input(request, handler):
    """Blocks the model call entirely if the latest user message trips OpenAI's
    moderation API -- deterministic, cheap, runs before any RAG retrieval or generation."""
    last_user_text = request.messages[-1].content
    result = _get_moderation_client().moderations.create(
        model="omni-moderation-latest", input=last_user_text
    )
    if result.results[0].flagged:
        return AIMessage(content="I can't help with that request.")
    return handler(request)


@wrap_model_call
def capture_telemetry(request, handler):
    """Instrumentation, not behavior -- records exactly what got sent to the model and
    what came back, then attaches it to the response's own `response_metadata`. That's
    the same trick `search_knowledge_base`'s artifact uses: ride along on a message
    object that's already being checkpointed, instead of inventing a separate
    side-channel that would only work for the live turn and go stale on reload.

    Placed LAST in the middleware list (see build_agent) so `request.messages` here is
    the final, fully-assembled prompt -- after PII redaction, after the personalized
    system prompt, after summarization has (maybe) already trimmed the history. Any
    agent turn with a tool call triggers this twice: once for the call that decides to
    invoke search_knowledge_base, once for the call that writes the final answer -- both
    get their own telemetry, which is itself worth showing students.
    """
    full_history = request.state.get("messages", []) if request.state else []
    sent_messages = request.messages
    summarized_this_turn = len(sent_messages) < len(full_history)

    t0 = time.perf_counter()
    response = handler(request)
    latency_s = round(time.perf_counter() - t0, 3)

    ai_messages = [m for m in response.result if isinstance(m, AIMessage)]
    usage = None
    if ai_messages and ai_messages[-1].usage_metadata:
        usage = dict(ai_messages[-1].usage_metadata)

    telemetry = {
        "model": MODEL,
        "latency_s": latency_s,
        "messages_sent": len(sent_messages),
        "messages_in_full_history": len(full_history),
        "summarized_this_turn": summarized_this_turn,
        "memory_policy": MEMORY_POLICY,
        "system_prompt": request.system_message.text if request.system_message else None,
        "messages_preview": [
            {
                "role": m.type,
                "content": (m.content if isinstance(m.content, str) else str(m.content))[:600],
            }
            for m in sent_messages
        ],
        "usage": usage,
        "had_tool_calls": bool(ai_messages and ai_messages[-1].tool_calls),
    }
    if usage:
        telemetry["estimated_cost_usd"] = round(
            usage.get("input_tokens", 0) / 1000 * PRICE_PER_1K_INPUT_TOKENS
            + usage.get("output_tokens", 0) / 1000 * PRICE_PER_1K_OUTPUT_TOKENS,
            6,
        )

    if ai_messages:
        ai_messages[-1].response_metadata = {
            **(ai_messages[-1].response_metadata or {}), "telemetry": telemetry,
        }
    return response


def build_agent(file_paths, db_dir="./memory_store",
                 chunking_strategy="fixed", chunk_size=500, chunk_overlap=80,
                 semantic_breakpoint_percentile=90,
                 top_k=8, top_n=4, min_rerank_score=MIN_RERANK_SCORE,
                 existing_store=None):
    """Ingest documents into a fresh hybrid index, then assemble the full production
    agent: RAG tool + durable memory + long-term memory + PII/moderation guardrails +
    resilience. Returns (agent, store, stack, stats, index, reranker) -- `stack` must
    stay alive for the lifetime of the agent (it owns the long-term memory DB
    connection); close it with `stack.close()` when the agent is no longer needed.
    `index` and `reranker` are returned so a UI can introspect the live vector/BM25
    store and run its own retrieval passes (e.g. for evaluation) without needing a
    second copy of either.

    `chunking_strategy` is `"fixed"` (RecursiveCharacterTextSplitter, governed by
    `chunk_size`/`chunk_overlap`) or `"semantic"` (groups sentences by topic shift,
    governed by `semantic_breakpoint_percentile` -- see semantic_chunk_documents in
    rag_pipeline.py for the algorithm). Semantic chunking needs an embedder, so
    HybridIndex is constructed before chunking (not after, like the fixed path) and
    its embedder is reused for chunking -- no second model/client to set up.

    Pass `existing_store` to reuse an already-open SqliteStore (e.g. one opened at app
    startup) so that long-term memories survive agent rebuilds.
    """
    db_dir = Path(db_dir)
    db_dir.mkdir(exist_ok=True)

    pages = []
    for path in file_paths:
        pages.extend(load_document(path))

    index = HybridIndex()
    if chunking_strategy == "semantic":
        chunks = semantic_chunk_documents(
            pages, index.encoder, breakpoint_percentile=semantic_breakpoint_percentile,
        )
    else:
        chunks = chunk_documents(pages, chunk_size, chunk_overlap)
    index.build(chunks)
    reranker = Reranker()
    search_tool = make_search_tool(index, reranker, top_k, top_n, min_rerank_score)
    summarize_tool = make_summarize_tool(index)

    # Durable short-term memory: conversation state survives a process restart.
    conn = sqlite3.connect(str(db_dir / "chat_memory.db"), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()

    # Durable long-term memory: reuse the caller's store if provided so facts are never
    # lost on rebuild; otherwise open a new one backed by the persistent db_dir.
    stack = ExitStack()
    if existing_store is not None:
        store = existing_store
    else:
        store = stack.enter_context(SqliteStore.from_conn_string(str(db_dir / "long_term_memory.db")))
        store.setup()

    agent = create_agent(
        # A real ChatOpenAI instance (not a bare model-name string) so we can force
        # stream_usage=True -- without it, OpenAI's streaming API silently omits token
        # counts, and the "tokens used" panel would go blank the moment the UI streams
        # a response instead of blocking on invoke().
        model=ChatOpenAI(model=MODEL, temperature=0, stream_usage=True),
        tools=[search_tool, summarize_tool],
        # No static system_prompt here — personalized_prompt (below in middleware)
        # builds it dynamically from RAG_SYSTEM_PROMPT + the user's long-term facts.
        # A static system_prompt would take precedence and the facts would never appear.
        context_schema=Context,
        checkpointer=checkpointer,
        store=store,
        middleware=[
            # 1. Deterministic, cheap checks first -- no LLM call needed to reject.
            PIIMiddleware("email", strategy="redact", apply_to_input=True),
            PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
            moderate_input,
            # 2. Personalization from long-term memory.
            personalized_prompt,
            # 3. Cost control -- summarize once a conversation gets long.
            SummarizationMiddleware(
                model=MODEL,
                trigger=("tokens", MEMORY_POLICY["trigger_tokens"]),
                keep=("messages", MEMORY_POLICY["keep_messages"]),
            ),
            # 4. Resilience -- survive a model-provider outage.
            ModelRetryMiddleware(max_retries=2),
            ModelFallbackMiddleware(FALLBACK_MODEL),
            # 5. Instrumentation -- last, so it sees the exact final request/response.
            capture_telemetry,
        ],
    )

    stats = {
        "files": len(file_paths), "pages": len(pages), "chunks": len(chunks),
        "chunking_strategy": chunking_strategy,
        "embedding_model": index.embedding_model_name,
        "embedding_dims": int(index._doc_emb.shape[1]) if index._doc_emb is not None else None,
        "vector_db": "Chroma (in-memory, cosine)", "sparse_index": "BM25 (bm25s, Lucene scoring)",
        # Retrieval settings are baked into search_tool's closure above, not stored
        # on index/reranker themselves -- recorded here so a UI (e.g. the
        # Evaluation tab) can reproduce exactly what the live agent is using
        # instead of reading possibly-since-changed sidebar sliders.
        "top_k": top_k, "top_n": top_n, "min_rerank_score": min_rerank_score,
    }
    return agent, store, stack, stats, index, reranker


def remember_fact(store, user_id: str, fact_id: str, text: str):
    """Seed a long-term fact about a user, recallable from any future conversation
    thread. In production this would be written by the agent itself (e.g. a
    `save_memory` tool) rather than called directly -- exposed here for the notebook/app
    demo of cross-session recall."""
    store.put(("memories", user_id), fact_id, {"text": text})


def record_thread(store, user_id: str, thread_id: str, preview: str):
    """Index a conversation thread under its owning user, so it can be listed and
    resumed later. The checkpointer itself doesn't know which user a thread_id belongs
    to (it's keyed purely by thread_id) -- this reuses the same persistent Store that
    backs long-term memory to add that missing per-user index. Only records once per
    thread: called on the first message, left alone after, so the preview always shows
    how a conversation started.
    """
    existing = store.get(("threads", user_id), thread_id)
    if existing is not None:
        return
    store.put(
        ("threads", user_id), thread_id,
        {"preview": preview[:80], "created_at": datetime.now(timezone.utc).isoformat()},
    )


def list_threads(store, user_id: str):
    """Return this user's conversation threads, most recently created first."""
    items = store.search(("threads", user_id))
    return sorted(items, key=lambda item: item.value["created_at"], reverse=True)
