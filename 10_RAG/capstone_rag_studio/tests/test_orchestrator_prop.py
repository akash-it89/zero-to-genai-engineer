"""Feature: rag-studio — Linear_Flow orchestrator property tests (Req 21).

Covers P19 (linear stage sequence equals canonical order, each present stage once,
no branching/looping), P11 (reproducible retrieval — identical authorized chunk ids
across two runs at temperature 0.0), and P21 (stages running local modules record
zero token usage/cost while API stages record measured usage). Req 19.4, 21.1, 21.3, 23.2.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from rag.cache import make_cache
from rag.config import PipelineConfig
from rag.governance import GovernanceFilter, InMemoryAccessPolicyProvider, InMemoryAuditLog
from rag.guardrails import make_guardrail
from rag.interfaces import (
    AccessPolicy,
    Candidate,
    Chunk,
    GenerationOutput,
    PipelineContext,
    Principal,
    Retriever,
)
from rag.orchestrator import CANONICAL_STAGE_ORDER, LinearFlow
from rag.post_retrieval import make_post_retrieval_processor
from rag.query_transform import make_query_transformer
from rag.rerank import NoneReranker


class _FakeRetriever(Retriever):
    """Deterministic retriever over a fixed 3-chunk corpus — no randomness (Req 23.2)."""

    mode = "fake"

    def __init__(self, chunks: list[Chunk]):
        self._candidates = [Candidate(chunk=c, score=1.0 - i * 0.1, rank=i) for i, c in enumerate(chunks)]

    def retrieve(self, query: str, top_k: int, ctx) -> list[Candidate]:
        return list(self._candidates)[:top_k]


class _FakeGenerationLLM:
    """Deterministic fake API-based generation stage recording measured token usage."""

    def generate(self, question: str, context_chunks: list[Chunk], history=None) -> GenerationOutput:
        return GenerationOutput(answer="a deterministic answer", citations=[], token_usage=17, cost_estimate=0.05)


def _build_ctx_and_config(request_id: str):
    chunks = [
        Chunk(id="c0", text="chunk zero", source="doc1"),
        Chunk(id="c1", text="chunk one", source="doc1"),
        Chunk(id="c2", text="chunk two", source="doc2"),
    ]
    policies = {
        "doc1": AccessPolicy(access_level="PUBLIC"),
        "doc2": AccessPolicy(access_level="PUBLIC"),
    }
    governance_filter = GovernanceFilter(InMemoryAccessPolicyProvider(policies))
    config = PipelineConfig(name="v1", top_k=10, rerank_top_k=3, temperature=0.0)
    principal = Principal(id="alice")
    extras = {
        "cache": make_cache("off"),
        "guardrail": make_guardrail("off"),
        "retriever": _FakeRetriever(chunks),
        "query_transformer": make_query_transformer("none"),
        "post_retrieval_processor": make_post_retrieval_processor("none"),
        "reranker": NoneReranker(),
        "governance_filter": governance_filter,
        "audit_sink": InMemoryAuditLog(),
    }
    ctx = PipelineContext(
        config=config,
        principal=principal,
        request_id=request_id,
        generation_llm=_FakeGenerationLLM(),
        extras=extras,
    )
    return config, principal, ctx


@given(question=st.text(min_size=1, max_size=30))
@settings(max_examples=30, deadline=None)
def test_p19_canonical_stage_order_each_stage_once(question):
    config, principal, ctx = _build_ctx_and_config(request_id="req-order")
    LinearFlow().run(config, question, principal, ctx)

    trace = ctx.extras["traces"]["req-order"]
    stage_names = [s.stage for s in trace.stages]

    assert stage_names == CANONICAL_STAGE_ORDER
    assert len(stage_names) == len(set(stage_names))  # each stage exactly once


@given(question=st.text(min_size=1, max_size=30))
@settings(max_examples=30, deadline=None)
def test_p11_reproducible_retrieval_across_two_runs(question):
    config1, principal1, ctx1 = _build_ctx_and_config(request_id="req-a")
    config2, principal2, ctx2 = _build_ctx_and_config(request_id="req-b")

    result1 = LinearFlow().run(config1, question, principal1, ctx1)
    result2 = LinearFlow().run(config2, question, principal2, ctx2)

    ids1 = [c.id for c in result1.reranked_chunks]
    ids2 = [c.id for c in result2.reranked_chunks]
    assert ids1 == ids2

    retrieved_ids1 = [c.id for c in result1.retrieved_chunks]
    retrieved_ids2 = [c.id for c in result2.retrieved_chunks]
    assert retrieved_ids1 == retrieved_ids2


@given(question=st.text(min_size=1, max_size=30))
@settings(max_examples=30, deadline=None)
def test_p21_local_stages_zero_cost_api_stage_measured(question):
    config, principal, ctx = _build_ctx_and_config(request_id="req-cost")
    LinearFlow().run(config, question, principal, ctx)

    trace = ctx.extras["traces"]["req-cost"]
    by_stage = {s.stage: s for s in trace.stages}

    for name in ("input_guardrail", "query_transform", "retrieval", "governance",
                 "post_retrieval", "rerank", "output_guardrail"):
        assert by_stage[name].token_usage == 0
        assert by_stage[name].cost_estimate == 0.0

    assert by_stage["generate"].token_usage == 17
    assert by_stage["generate"].cost_estimate == 0.05
    assert trace.total_token_usage == 17
    assert trace.total_cost_estimate == 0.05
