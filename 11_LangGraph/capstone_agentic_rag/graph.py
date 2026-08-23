"""
Self-Correcting Agentic RAG -- the LangGraph built in Notebook 03, saved as an importable
module so the notebook and the Streamlit app (app.py) share one graph instead of drifting
apart.

This module is the "everything Module 10 taught, wired into one agent" deliverable:

    Module 10 tool/technique                         -> where it's used here
    ------------------------------------------------  ---------------------------------------
    HybridIndex (dense Chroma + BM25, RRF fusion)      retrieve()            [Notebook 05/06/07]
    Cross-encoder reranking                            retrieve()            [Notebook 08]
    min_rerank_score guardrail (ProductionRAGChatbot)  grade_documents()     [Notebook 13]
    RAGAS Faithfulness (LLM-judge fallback if unavail) check_groundedness() [Notebook 09 / S10e]
    Condense-question memory                           condense()            [Notebook 13]
    Token-budget trimming                              trim_history()        [Notebook 11 S5b]
    Long-term memory (Store)                           recall_preferences()  [Notebook 11 S6]
    Resilience (retry-with-backoff)                     resilient_invoke()   [Notebook 11 S10]
    Structured output (Pydantic schema)                extract_structured_citations() [NB11 S11]
    Human-in-the-loop (interrupt/Command)              human_escalation()    [Notebook 11 S9]
    Checkpointer (short-term, resumable memory)        build_graph()         [Notebook 11 S3/S4]

Everything under "Module 10 tool/technique" is imported or replicated with the SAME API used
when it was taught, not reinvented -- see the inline comments on each node for the exact
notebook/section it corresponds to.

Graph:
    trim_history -> recall_preferences -> condense -> retrieve -> grade_documents
                                                            ^             |
                                                            |        sufficient / insufficient
                                                            |             v
                                                      rewrite_query <-----+---> generate -> check_groundedness
                                                                                    ^              |
                                                                                    |         grounded / not
                                                                                    |              v
                                                                              regenerate_bump <-----+
                                                                                                     |
                                                                        (retries exhausted, either check)
                                                                                                     v
                                                                              human_escalation --interrupt()--> finalize -> END
"""

import logging
import sys
import time
import warnings
from pathlib import Path
from typing import Annotated, Optional

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt, Command
from langchain_core.messages import AIMessage, RemoveMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

RAG_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "10_RAG" / "notebooks" / "production_rag_chatbot"
sys.path.insert(0, str(RAG_PIPELINE_DIR))

from rag_pipeline import (  # noqa: E402
    HybridIndex, Reranker, load_document, chunk_documents,
    format_sources, ANSWER_PROMPT, CONDENSE_PROMPT,
)

# ---- RAGAS (Notebook 09 / S10e) -- optional, with a graceful LLM-judge fallback ----------
# Mirrors the exact compatibility shim Notebook 09 uses: ragas 0.4.x imports a
# langchain_community path that moved in LangChain 1.x; we never touch Vertex AI, so a
# harmless stub unblocks the import instead of pinning an older langchain-community.
try:
    import types as _types
    if "langchain_community.chat_models.vertexai" not in sys.modules:
        _shim = _types.ModuleType("langchain_community.chat_models.vertexai")

        class _ChatVertexAIStub:  # never instantiated -- we only ever use OpenAI
            pass

        _shim.ChatVertexAI = _ChatVertexAIStub
        sys.modules["langchain_community.chat_models.vertexai"] = _shim

    # NOTE: `ragas.metrics.Faithfulness` + `LangchainLLMWrapper` is the exact API Notebook 09
    # (S10e) teaches, and is what this line intentionally still uses for consistency with that
    # session -- ragas 0.4.x prints a DeprecationWarning pointing at `ragas.metrics.collections`,
    # but that newer API requires an `instructor`-wrapped LLM (a dependency + pattern not used
    # anywhere else in this course) for no teaching benefit here. Revisit if the old path is
    # ever actually removed, not just deprecated.
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import Faithfulness
    from ragas.llms import LangchainLLMWrapper

    HAVE_RAGAS = True
except ImportError:
    HAVE_RAGAS = False
    logger.warning("ragas not installed -- check_groundedness() will fall back to an LLM-judge prompt.")

MAX_REWRITES = 2
MAX_REGENERATE = 1
MIN_RERANK_SCORE = -9.5          # same heuristic guardrail threshold as ProductionRAGChatbot (Notebook 13)
FAITHFULNESS_THRESHOLD = 0.7     # RAGAS Faithfulness score below this -> "not_grounded"
MAX_HISTORY_MESSAGES = 12        # token-budget cap on stored conversation (Notebook 11, Section 5b)
DEFAULT_ANSWER_STYLE = "detailed"

GRADE_PROMPT = """Are the SOURCES below sufficient to answer the QUESTION well? Answer with
exactly one word: SUFFICIENT or INSUFFICIENT.

QUESTION: {question}

SOURCES:
{sources}"""

REWRITE_PROMPT = """The QUESTION below did not retrieve sufficient sources from the knowledge
base. Rewrite it to be more specific and retrieval-friendly. Return ONLY the rewritten
question, nothing else.

QUESTION: {question}"""

# Used only when ragas isn't installed -- see check_groundedness().
GROUNDEDNESS_FALLBACK_PROMPT = """Does the ANSWER rely ONLY on facts present in the SOURCES,
with no invented details? Answer with exactly one word: GROUNDED or NOT_GROUNDED.

SOURCES:
{sources}

ANSWER:
{answer}"""


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    standalone_question: str
    reranked: list
    grade: str
    rewrite_count: int
    answer: str
    groundedness: str
    faithfulness_score: Optional[float]
    regenerate_count: int
    answer_style: str


def remember_answer_style(store: InMemoryStore, user_id: str, style: str) -> None:
    """Seed a long-term preference directly -- the same 'as if captured yesterday' pattern
    Notebook 11 Section 6 uses to demonstrate Store recall across brand-new threads."""
    if style not in ("concise", "detailed"):
        raise ValueError("style must be 'concise' or 'detailed'")
    store.put(("preferences", user_id), "answer_style", {"value": style})


def build_graph(model: str = "gpt-4o-mini", data_dir: Path | None = None, user_id: str = "default-user"):
    """Build and compile the Self-Correcting Agentic RAG graph.

    `data_dir` should contain the file(s) to index; if omitted, falls back to Module 10's
    sample_report.pdf so the graph is runnable with zero setup.
    """
    llm = ChatOpenAI(model=model, temperature=0)

    index = HybridIndex()
    reranker = Reranker()
    store = InMemoryStore()

    faithfulness_metric = None
    if HAVE_RAGAS:
        faithfulness_metric = Faithfulness(llm=LangchainLLMWrapper(llm))

    def ingest(file_paths: list[str]) -> dict:
        pages = []
        for path in file_paths:
            pages.extend(load_document(path))
        chunks = chunk_documents(pages, chunk_size=500, chunk_overlap=80)
        index.build(chunks)
        return {"files": len(file_paths), "pages": len(pages), "chunks": len(chunks)}

    if data_dir is None:
        data_dir = Path(__file__).resolve().parents[2] / "10_RAG" / "notebooks" / "data"
    sample = data_dir / "sample_report.pdf"
    if sample.exists():
        ingest([str(sample)])

    def resilient_invoke(prompt: str, max_retries: int = 2, backoff: float = 1.5):
        """Same idea as Notebook 11's ModelRetryMiddleware(max_retries=2, backoff_factor=2.0)
        -- applied by hand, since these are plain StateGraph nodes, not a create_agent loop."""
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                return llm.invoke(prompt)
            except Exception as e:  # noqa: BLE001 -- deliberately broad: any transient provider error
                last_err = e
                logger.warning("LLM call failed (attempt %d/%d): %s", attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(backoff ** attempt)
        raise last_err

    # ---- Nodes --------------------------------------------------------
    def trim_history(state: AgentState) -> dict:
        """Token-budget management (Notebook 11, Section 5b): cap the STORED message list,
        not just what a node happens to read, so the checkpointer's state can't grow forever."""
        messages = state["messages"]
        if len(messages) <= MAX_HISTORY_MESSAGES:
            return {}
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages[-MAX_HISTORY_MESSAGES:]]}

    def recall_preferences(state: AgentState, *, store) -> dict:
        """Long-term memory (Notebook 11, Section 6): a Store lookup, keyed by user_id, not by
        thread_id -- so a brand-new conversation still recalls a preference set days ago."""
        item = store.get(("preferences", user_id), "answer_style")
        return {"answer_style": item.value["value"] if item else DEFAULT_ANSWER_STYLE}

    def condense(state: AgentState) -> dict:
        """Module 10's condense-question pattern (Notebook 13), reading history from graph
        state instead of a hand-maintained self.history list."""
        question = state["messages"][-1].content
        history = state["messages"][:-1]
        if not history:
            standalone = question
        else:
            history_text = "\n".join(f"{m.type}: {m.content}" for m in history[-6:])
            standalone = resilient_invoke(
                CONDENSE_PROMPT.format(history=history_text, question=question)
            ).content.strip()
        return {"standalone_question": standalone, "rewrite_count": 0, "regenerate_count": 0}

    def retrieve(state: AgentState) -> dict:
        """Module 10's HybridIndex + Reranker (Notebooks 05-08), called exactly as
        ProductionRAGChatbot.chat() does."""
        candidates = index.search(state["standalone_question"], k=8)
        reranked = reranker.rerank(state["standalone_question"], candidates, top_n=4)
        return {"reranked": reranked}

    def grade_documents(state: AgentState) -> dict:
        """Two guardrails, cheapest first:
        1. The exact min_rerank_score heuristic from ProductionRAGChatbot (Notebook 13) --
           free, no LLM call, catches the common "nothing relevant" case immediately.
        2. An LLM-judge sufficiency check for the harder, ambiguous cases the heuristic can't
           see (e.g. plausible-looking chunks that don't actually cover the question)."""
        reranked = state["reranked"]
        if not reranked or reranked[0][1] < MIN_RERANK_SCORE:
            return {"grade": "insufficient"}
        sources = format_sources(reranked)
        verdict = resilient_invoke(
            GRADE_PROMPT.format(question=state["standalone_question"], sources=sources)
        ).content.strip().upper()
        grade = "insufficient" if "INSUFFICIENT" in verdict else "sufficient"
        return {"grade": grade}

    def rewrite_query(state: AgentState) -> dict:
        rewritten = resilient_invoke(REWRITE_PROMPT.format(question=state["standalone_question"])).content.strip()
        return {"standalone_question": rewritten, "rewrite_count": state.get("rewrite_count", 0) + 1}

    def generate(state: AgentState) -> dict:
        """Module 10's ANSWER_PROMPT and format_sources (Notebook 13), unmodified, plus one
        addition: the long-term `answer_style` preference adjusts verbosity."""
        history_text = "\n".join(f"{m.type}: {m.content}" for m in state["messages"][:-1][-6:])
        prompt = ANSWER_PROMPT.format(
            sources=format_sources(state["reranked"]), history=history_text,
            question=state["standalone_question"],
        )
        if state.get("answer_style") == "concise":
            prompt += "\n\n(The user prefers concise answers -- 2 sentences maximum.)"
        answer = resilient_invoke(prompt).content.strip()
        return {"answer": answer}

    def check_groundedness(state: AgentState) -> dict:
        """RAGAS Faithfulness (Notebook 09 / S10e) when available -- the exact metric that
        session taught for hallucination detection, now used live as a gate instead of an
        offline evaluation. Falls back to an LLM-judge prompt if ragas isn't installed, so the
        graph degrades gracefully rather than hard-failing on a missing optional dependency."""
        sources_text = format_sources(state["reranked"])
        if HAVE_RAGAS and faithfulness_metric is not None:
            sample = SingleTurnSample(
                user_input=state["standalone_question"],
                response=state["answer"],
                retrieved_contexts=[c["text"] for c, _ in state["reranked"]],
            )
            score = faithfulness_metric.single_turn_score(sample)
            groundedness = "grounded" if score >= FAITHFULNESS_THRESHOLD else "not_grounded"
            return {"groundedness": groundedness, "faithfulness_score": round(float(score), 3)}

        verdict = resilient_invoke(
            GROUNDEDNESS_FALLBACK_PROMPT.format(sources=sources_text, answer=state["answer"])
        ).content.strip().upper()
        groundedness = "not_grounded" if "NOT_GROUNDED" in verdict else "grounded"
        return {"groundedness": groundedness, "faithfulness_score": None}

    def regenerate_bump(state: AgentState) -> dict:
        return {"regenerate_count": state.get("regenerate_count", 0) + 1}

    def human_escalation(state: AgentState) -> dict:
        """Human-in-the-loop (Notebook 11, Section 9): the same interrupt()/Command(resume=...)
        primitive HumanInTheLoopMiddleware is built from, applied here to a decision no
        prebuilt middleware covers -- "we've retried and still can't ground an answer."""
        guidance = interrupt({
            "reason": "Could not retrieve/generate a grounded answer after retrying.",
            "question": state["standalone_question"],
            "best_effort_answer": state.get("answer"),
            "rewrite_count": state.get("rewrite_count", 0),
            "regenerate_count": state.get("regenerate_count", 0),
        })
        if guidance and guidance.get("human_answer"):
            return {"answer": guidance["human_answer"], "groundedness": "human_provided"}
        return {
            "answer": "I don't have enough grounded information in this document to answer "
                       "confidently, and no human guidance was provided.",
            "groundedness": "refused",
        }

    def finalize(state: AgentState) -> dict:
        return {"messages": [AIMessage(content=state["answer"])]}

    # ---- Wire the graph --------------------------------------------------------
    builder = StateGraph(AgentState)
    for name, fn in [
        ("trim_history", trim_history), ("recall_preferences", recall_preferences),
        ("condense", condense), ("retrieve", retrieve), ("grade_documents", grade_documents),
        ("rewrite_query", rewrite_query), ("generate", generate),
        ("check_groundedness", check_groundedness), ("regenerate_bump", regenerate_bump),
        ("human_escalation", human_escalation), ("finalize", finalize),
    ]:
        builder.add_node(name, fn)

    builder.add_edge(START, "trim_history")
    builder.add_edge("trim_history", "recall_preferences")
    builder.add_edge("recall_preferences", "condense")
    builder.add_edge("condense", "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    builder.add_conditional_edges("grade_documents", route_after_grade_pure, {
        "generate": "generate", "rewrite_query": "rewrite_query", "human_escalation": "human_escalation",
    })
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_edge("generate", "check_groundedness")
    builder.add_conditional_edges("check_groundedness", route_after_groundedness_pure, {
        "finalize": "finalize", "regenerate_bump": "regenerate_bump", "human_escalation": "human_escalation",
    })
    builder.add_edge("regenerate_bump", "generate")
    builder.add_edge("human_escalation", "finalize")
    builder.add_edge("finalize", END)

    graph = builder.compile(checkpointer=InMemorySaver(), store=store)
    return graph, index, reranker, store, ingest


# ---- Pure routing functions -----------------------------------------------------
# Kept independent of build_graph()'s closures (no llm/index/store needed) so they're testable
# in isolation -- see tests/test_graph.py. The in-closure route_after_grade/route_after_groundedness
# above just delegate here; the split exists purely for testability, not behavior.

def route_after_grade_pure(state: AgentState) -> str:
    if state["grade"] == "sufficient":
        return "generate"
    if state.get("rewrite_count", 0) < MAX_REWRITES:
        return "rewrite_query"
    return "human_escalation"


def route_after_groundedness_pure(state: AgentState) -> str:
    if state["groundedness"] == "grounded":
        return "finalize"
    if state.get("regenerate_count", 0) < MAX_REGENERATE:
        return "regenerate_bump"
    return "human_escalation"


# ---- Structured output (Notebook 11, Section 11) ---------------------------------
# A separate, optional utility rather than a graph node: the user-facing answer stays plain,
# streamable text (generate() above); this is what you'd call when a DOWNSTREAM system (a
# ticketing queue, a citations API) needs a validated schema instead of prose. Same idea as
# Notebook 11's `response_format=ProviderStrategy(schema=SupportTicket)` on create_agent,
# applied via `llm.with_structured_output()` since this isn't a create_agent loop.

def extract_structured_citations(question: str, answer: str, reranked: list, model: str = "gpt-4o-mini"):
    """Parse a finished answer + its sources into a validated Pydantic object:
    {question, answer, citations: [{rank, source, page}]}. Returns a GroundedAnswer instance.
    """
    from pydantic import BaseModel, Field

    class CitationModel(BaseModel):
        rank: int = Field(description="1-based rank among the sources actually used")
        source: str
        page: int

    class GroundedAnswer(BaseModel):
        answer: str
        citations: list[CitationModel] = Field(description="Sources the answer actually cites")

    llm = ChatOpenAI(model=model, temperature=0)
    structured_llm = llm.with_structured_output(GroundedAnswer)

    sources = format_sources(reranked)
    prompt = (
        "Given the QUESTION, ANSWER, and numbered SOURCES below, extract which sources the "
        "answer actually cites.\n\nQUESTION: {question}\n\nANSWER: {answer}\n\nSOURCES:\n{sources}"
    ).format(question=question, answer=answer, sources=sources)
    return structured_llm.invoke(prompt)
