"""
Tests for the Self-Correcting Agentic RAG graph (../graph.py).

Same testing philosophy as Module 10's Notebook 11 (Section 13, "trajectory assertion" tests)
and Module 09's loop-engineering principle ("stop conditions must be deterministic"): assert
on the PATH the graph took -- which nodes fired, in what order, with what retry counts -- not
just on a final answer string, since a correct-looking answer reached by skipping the grading
or groundedness step is a bug, not a pass.

Run with:
    pytest 11_LangGraph/capstone_agentic_rag/tests/test_graph.py -v

No OPENAI_API_KEY or network access required -- rag_pipeline's heavy retrieval dependencies
and ChatOpenAI are replaced with fakes before graph.py is imported, so these tests exercise
the REAL control-flow code in graph.py, not a reimplementation of it.
"""

import sys
import types
from pathlib import Path

import pytest

os_env_key = "OPENAI_API_KEY"
import os
os.environ.setdefault(os_env_key, "sk-test-key-for-tests-only")

CAPSTONE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAPSTONE_DIR))


# ---- Fake rag_pipeline (stands in for the real, ML-dependency-heavy module) ---------------
def _install_fake_rag_pipeline():
    fake_rp = types.ModuleType("rag_pipeline")

    class FakeHybridIndex:
        def build(self, chunks):
            self.chunks = chunks

        def search(self, query, k=8):
            if "hopeless" in query:
                return []
            return [{"source": "doc", "page": 1, "text": "some real retrieved content"}]

    class FakeReranker:
        def rerank(self, query, candidates, top_n=4):
            if not candidates:
                return []
            return [(c, 5.0) for c in candidates][:top_n]

    fake_rp.HybridIndex = FakeHybridIndex
    fake_rp.Reranker = FakeReranker
    fake_rp.load_document = lambda path: [{"text": "fake page", "source": "fake.pdf", "page": 1}]
    fake_rp.chunk_documents = lambda pages, chunk_size=500, chunk_overlap=80: [
        {"text": p["text"], "source": p["source"], "page": p["page"]} for p in pages
    ]
    fake_rp.format_sources = lambda reranked: "\n".join(
        f"[{i + 1}] {c['text']}" for i, (c, _) in enumerate(reranked)
    )
    fake_rp.ANSWER_PROMPT = "Q:{question} H:{history} S:{sources}"
    fake_rp.CONDENSE_PROMPT = "H:{history} Q:{question}"
    sys.modules["rag_pipeline"] = fake_rp


_install_fake_rag_pipeline()

import graph as g  # noqa: E402  -- import after the fake rag_pipeline is registered

g.HAVE_RAGAS = False  # force the LLM-judge fallback path; ragas needs real async LLM calls


# ---- Fake ChatOpenAI.invoke -- deterministic responses keyed off prompt content -----------
class _FakeResponse:
    def __init__(self, content):
        self.content = content


def _install_fake_llm(call_log):
    from langchain_openai import ChatOpenAI

    def fake_invoke(self, prompt, *a, **kw):
        text = prompt if isinstance(prompt, str) else str(prompt)
        call_log.append(text)
        if "SUFFICIENT or INSUFFICIENT" in text:
            return _FakeResponse("INSUFFICIENT" if "hopeless" in text else "SUFFICIENT")
        if "GROUNDED or NOT_GROUNDED" in text:
            return _FakeResponse("GROUNDED")
        if "Rewrite it" in text:
            return _FakeResponse("hopeless question, rewritten to be more specific")
        if "H:" in text and "Q:" in text and "S:" not in text:  # CONDENSE_PROMPT shape
            return _FakeResponse("standalone question")
        return _FakeResponse("a grounded generated answer")

    ChatOpenAI.invoke = fake_invoke


@pytest.fixture
def built_graph(tmp_path):
    call_log = []
    _install_fake_llm(call_log)
    graph, index, reranker, store, ingest = g.build_graph(data_dir=tmp_path)
    ingest(["fake.pdf"])
    return graph, store, call_log


# ---- Pure router function tests (no graph, no LLM -- just state -> next-node) -------------

def test_route_after_grade_sufficient_goes_to_generate():
    assert g.route_after_grade_pure({"grade": "sufficient"}) == "generate"


def test_route_after_grade_insufficient_retries_before_escalating():
    state = {"grade": "insufficient", "rewrite_count": 0}
    assert g.route_after_grade_pure(state) == "rewrite_query"

    state = {"grade": "insufficient", "rewrite_count": g.MAX_REWRITES}
    assert g.route_after_grade_pure(state) == "human_escalation"


def test_route_after_groundedness_grounded_finalizes():
    assert g.route_after_groundedness_pure({"groundedness": "grounded"}) == "finalize"


def test_route_after_groundedness_not_grounded_retries_before_escalating():
    state = {"groundedness": "not_grounded", "regenerate_count": 0}
    assert g.route_after_groundedness_pure(state) == "regenerate_bump"

    state = {"groundedness": "not_grounded", "regenerate_count": g.MAX_REGENERATE}
    assert g.route_after_groundedness_pure(state) == "human_escalation"


# ---- Full graph trajectory tests (real graph.py, fake retrieval + fake LLM) ----------------

def test_normal_question_reaches_finalize_without_retries(built_graph):
    from langchain_core.messages import HumanMessage

    graph, store, _ = built_graph
    config = {"configurable": {"thread_id": "t-normal"}}
    result = graph.invoke({"messages": [HumanMessage(content="what does the report say?")]}, config)

    assert "__interrupt__" not in result
    state = graph.get_state(config).values
    assert state["grade"] == "sufficient"
    assert state["groundedness"] == "grounded"
    assert state["rewrite_count"] == 0
    assert state["regenerate_count"] == 0
    assert result["messages"][-1].content == "a grounded generated answer"


def test_unanswerable_question_exhausts_retries_and_pauses_for_a_human(built_graph):
    from langchain_core.messages import HumanMessage

    graph, store, _ = built_graph
    config = {"configurable": {"thread_id": "t-escalate"}}
    result = graph.invoke({"messages": [HumanMessage(content="hopeless question")]}, config)

    assert "__interrupt__" in result, "expected the graph to pause for human input"
    payload = result["__interrupt__"][0].value
    assert payload["rewrite_count"] == g.MAX_REWRITES
    assert payload["reason"].startswith("Could not retrieve")


def test_resuming_an_escalation_with_human_guidance_finalizes_that_answer(built_graph):
    from langchain_core.messages import HumanMessage
    from langgraph.types import Command

    graph, store, _ = built_graph
    config = {"configurable": {"thread_id": "t-resume"}}
    graph.invoke({"messages": [HumanMessage(content="hopeless question")]}, config)

    resumed = graph.invoke(Command(resume={"human_answer": "the human-provided answer"}), config)
    assert resumed["messages"][-1].content == "the human-provided answer"
    assert graph.get_state(config).values["groundedness"] == "human_provided"


def test_resuming_an_escalation_with_no_guidance_falls_back_to_honest_refusal(built_graph):
    from langchain_core.messages import HumanMessage
    from langgraph.types import Command

    graph, store, _ = built_graph
    config = {"configurable": {"thread_id": "t-resume-refuse"}}
    graph.invoke({"messages": [HumanMessage(content="hopeless question")]}, config)

    resumed = graph.invoke(Command(resume={"human_answer": None}), config)
    assert "don't have enough grounded information" in resumed["messages"][-1].content
    assert graph.get_state(config).values["groundedness"] == "refused"


def test_long_term_store_preference_reaches_the_generate_prompt(built_graph):
    from langchain_core.messages import HumanMessage

    graph, store, call_log = built_graph
    g.remember_answer_style(store, "default-user", "concise")

    # A BRAND-NEW thread that never mentioned any preference should still recall it.
    config = {"configurable": {"thread_id": "t-brand-new-thread"}}
    graph.invoke({"messages": [HumanMessage(content="what does the report say?")]}, config)

    assert any("concise answers" in call for call in call_log)


def test_conversation_history_is_capped_not_unbounded(built_graph):
    from langchain_core.messages import HumanMessage

    graph, store, _ = built_graph
    config = {"configurable": {"thread_id": "t-long-conversation"}}
    for i in range(10):
        graph.invoke({"messages": [HumanMessage(content=f"question {i}")]}, config)

    stored_messages = graph.get_state(config).values["messages"]
    assert len(stored_messages) <= g.MAX_HISTORY_MESSAGES + 2, (
        f"expected trim_history to cap growth, got {len(stored_messages)} messages"
    )


def test_remember_answer_style_rejects_invalid_values():
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    with pytest.raises(ValueError):
        g.remember_answer_style(store, "user-1", "sarcastic")
