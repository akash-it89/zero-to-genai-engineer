"""Feature: rag-studio — pipeline-stage invariant property tests.

Part 1: P13 chunk-build invariants (Req 3.5, 3.6).
Part 2: P16 contextual compression only removes/never fabricates, caps
tokens (Req 16.2, 17.3, 17.4, 17.6, 17.7).
Part 3 (this wave): P14 reranked chunks are a subset of the governance-filtered set
of size <= rerank_top_k; `none` yields the first rerank_top_k in retrieval order
(Req 4.6, 4.7, 22.4).
"""
from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from rag.ingest import MIN_CHUNK_CHARS, build_chunks
from rag.interfaces import AccessPolicy

_levels = st.sampled_from(["PUBLIC", "RESTRICTED", "PRIVATE"])
_policy = st.builds(
    AccessPolicy,
    access_level=_levels,
    owner=st.text(min_size=1, max_size=6),
    acl=st.lists(st.text(min_size=1, max_size=6), max_size=4),
)
# Distinct source names so chunk ids (source::index) are globally unique.
_doc = st.fixed_dictionaries({"text": st.text(min_size=0, max_size=400), "access_policy": _policy})
_docs = st.lists(_doc, min_size=1, max_size=6)


@settings(max_examples=100, deadline=None)
@given(docs=_docs, strategy=st.sampled_from(["recursive", "token", "markdown"]))
def test_p13_chunk_build_invariants(docs, strategy):
    # Feature: rag-studio, Property 13: every chunk has a unique id, records its source,
    # inherits that source's Access_Policy, and has length >= the minimum (shorter excluded).
    tagged = [{"text": d["text"], "source": f"doc{i}", "access_policy": d["access_policy"]}
              for i, d in enumerate(docs)]
    by_source = {t["source"]: t["access_policy"] for t in tagged}

    result = build_chunks(tagged, strategy=strategy, chunk_size=120, chunk_overlap=20)

    ids = [c.id for c in result.chunks]
    assert len(ids) == len(set(ids))                       # unique ids
    for c in result.chunks:
        assert c.source in by_source                       # records a real source
        assert c.access_policy is by_source[c.source]      # inherits the source policy
        assert len(c.text) >= MIN_CHUNK_CHARS              # minimum-length invariant


# ---------------------------------------------------------------------------
# Part 2 — P16 contextual compression (Req 16.2, 17.3, 17.4, 17.6, 17.7)
# ---------------------------------------------------------------------------

from rag.interfaces import Chunk, PipelineContext, Principal
from rag.post_retrieval import ContextualCompressionProcessor


class _FakeEmbedder:
    """Deterministic embedder: score is proportional to shared word count with the
    question, so relevance ordering is predictable without any provider/model call."""

    is_local = True

    def embed_query(self, text: str):
        words = set(text.lower().split())
        return np.array([1.0 if w in words else 0.0 for w in _VOCAB])

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]


_VOCAB = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]


@given(
    relevant_words=st.lists(st.sampled_from(_VOCAB), min_size=1, max_size=3, unique=True),
    irrelevant_chunks=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100, deadline=None)
def test_p16_compression_only_removes_and_bounds_tokens(relevant_words, irrelevant_chunks):
    question = " ".join(relevant_words)
    relevant_chunk = Chunk(id="r0", text=" ".join(relevant_words) + " " * 3, source="doc1")
    other_words = [w for w in _VOCAB if w not in relevant_words] or ["theta"]
    irrelevant = [
        Chunk(id=f"i{i}", text=other_words[i % len(other_words)], source="doc1")
        for i in range(irrelevant_chunks)
    ]
    chunks = [relevant_chunk, *irrelevant]

    ctx = PipelineContext(config=None, principal=Principal(id="u1"), embedder=_FakeEmbedder())
    processor = ContextualCompressionProcessor(relevance_floor=0.4, max_tokens=100000)
    result = processor.process(question, chunks, ctx)

    result_ids = {c.id for c in result}
    original_ids = {c.id for c in chunks}
    # Only removes — never introduces a chunk that wasn't in the input.
    assert result_ids <= original_ids
    # Never fabricates: every surviving chunk's text is byte-identical to the input.
    original_text = {c.id: c.text for c in chunks}
    for c in result:
        assert c.text == original_text[c.id]
    # The most relevant chunk always survives when it clears the floor.
    assert "r0" in result_ids


@given(n_chunks=st.integers(min_value=2, max_value=6))
@settings(max_examples=50, deadline=None)
def test_p16_compression_caps_total_tokens(n_chunks):
    long_text = "alpha " * 500   # ~500 tokens per chunk at the ~4-char approximation
    chunks = [Chunk(id=f"c{i}", text=long_text, source="doc1") for i in range(n_chunks)]
    ctx = PipelineContext(config=None, principal=Principal(id="u1"), embedder=_FakeEmbedder())
    processor = ContextualCompressionProcessor(relevance_floor=0.0, max_tokens=600)
    result = processor.process("alpha", chunks, ctx)
    # Always keeps at least one chunk even if it alone exceeds the cap.
    assert len(result) >= 1
    # With a 600-token budget and ~500 tokens/chunk, at most 2 chunks fit.
    assert len(result) <= 2


# ---------------------------------------------------------------------------
# Part 3 — P14 rerank bounding (Req 4.6, 4.7, 22.4)
# ---------------------------------------------------------------------------

from rag.rerank import NoneReranker


@given(
    n_chunks=st.integers(min_value=0, max_value=10),
    top_k=st.integers(min_value=0, max_value=6),
)
@settings(max_examples=100, deadline=None)
def test_p14_none_reranker_is_subset_capped_and_order_preserving(n_chunks, top_k):
    chunks = [Chunk(id=f"c{i}", text=f"text {i}", source="doc1") for i in range(n_chunks)]
    reranker = NoneReranker()
    result = reranker.rerank("any question", chunks, top_k)

    # Subset of the governance-filtered input set.
    assert {c.id for c in result} <= {c.id for c in chunks}
    # Size bounded by rerank_top_k.
    assert len(result) <= top_k
    assert len(result) <= len(chunks)
    # `none` preserves retrieval order: the first rerank_top_k chunks, in order.
    assert result == chunks[:top_k]
