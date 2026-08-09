"""Retriever modes: dense, BM25, and two hybrid fusions (Req 4.1-4.4).

Retrievers return raw ``Candidate`` lists for the Governance_Filter to screen next
(governance always runs downstream of retrieval, never inside it — Req 11.8). Only
:mod:`rag.interfaces` is imported at module scope; ``bm25s``/``PyStemmer`` are
imported lazily so the module stays light (Req 12.6).
"""
from __future__ import annotations

from typing import Sequence

from rag.interfaces import Candidate, Chunk, PipelineContext, Retriever, source_prefixed_text


# ---------------------------------------------------------------------------
# Dense retrieval (Req 4.1)
# ---------------------------------------------------------------------------

class DenseRetriever(Retriever):
    mode = "dense"

    def retrieve(self, query: str, top_k: int, ctx: PipelineContext) -> list[Candidate]:
        query_vec = ctx.embedder.embed_query(query)
        return ctx.vector_store.search(query_vec, top_k)


# ---------------------------------------------------------------------------
# Sparse BM25 retrieval (Req 4.2) — local, free
# ---------------------------------------------------------------------------

class Bm25Retriever(Retriever):
    """Keyword retrieval over the full corpus of indexed chunks.

    Built lazily on first use from ``ctx.extras['all_chunks']`` (populated at index
    time by the façade), since BM25 needs the whole corpus rather than a vector index.
    """

    mode = "bm25"
    is_local = True

    def __init__(self):
        self._retriever = None
        self._chunks: list[Chunk] = []
        self._stemmer = None

    def _ensure_built(self, chunks: Sequence[Chunk]) -> None:
        if self._retriever is not None and self._chunks == list(chunks):
            return
        import bm25s
        import Stemmer

        self._stemmer = Stemmer.Stemmer("english")
        self._chunks = list(chunks)
        # Tokenize the source-prefixed text (not raw c.text) so a chunk's own document
        # identity counts as a keyword match — otherwise a chunk from the *wrong*
        # document that happens to mention the right one by name can out-rank it on
        # pure term frequency alone (see rag.interfaces.source_prefixed_text).
        corpus_tokens = bm25s.tokenize([source_prefixed_text(c) for c in self._chunks], stemmer=self._stemmer)
        self._retriever = bm25s.BM25()
        self._retriever.index(corpus_tokens)

    def retrieve(self, query: str, top_k: int, ctx: PipelineContext) -> list[Candidate]:
        import bm25s

        chunks: list[Chunk] = ctx.extras.get("all_chunks", [])
        if not chunks:
            return []
        self._ensure_built(chunks)
        query_tokens = bm25s.tokenize([query], stemmer=self._stemmer)
        k = min(top_k, len(chunks))
        if k == 0:
            return []
        results, scores = self._retriever.retrieve(query_tokens, k=k)
        out = []
        for rank, (idx, score) in enumerate(zip(results[0], scores[0])):
            out.append(Candidate(chunk=self._chunks[int(idx)], score=float(score), rank=rank))
        return out


# ---------------------------------------------------------------------------
# Hybrid fusion (Req 4.3, 4.4)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    dense: list[Candidate], sparse: list[Candidate], k: int, rrf_k: int = 60
) -> list[Candidate]:
    """RRF: score(doc) = sum over lists of 1 / (rrf_k + rank_in_list). Req 4.3."""
    scores: dict[str, float] = {}
    chunk_by_id: dict[str, Chunk] = {}
    for candidates in (dense, sparse):
        for cand in candidates:
            cid = cand.chunk.id
            chunk_by_id[cid] = cand.chunk
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + cand.rank + 1)
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
    return [
        Candidate(chunk=chunk_by_id[cid], score=score, rank=rank)
        for rank, (cid, score) in enumerate(ordered)
    ]


def weighted_fusion(dense: list[Candidate], sparse: list[Candidate], k: int, alpha: float) -> list[Candidate]:
    """Weighted score fusion: alpha*dense_score + (1-alpha)*sparse_score. Req 4.4.

    Scores are min-max normalized per-list first so the two scales are comparable.
    """
    def _normalize(cands: list[Candidate]) -> dict[str, float]:
        if not cands:
            return {}
        vals = [c.score for c in cands]
        lo, hi = min(vals), max(vals)
        spread = (hi - lo) or 1.0
        return {c.chunk.id: (c.score - lo) / spread for c in cands}

    dense_norm = _normalize(dense)
    sparse_norm = _normalize(sparse)
    chunk_by_id: dict[str, Chunk] = {c.chunk.id: c.chunk for c in (*dense, *sparse)}

    # Deterministic id order (Req 23.2 reproducibility) — iterate dense-then-sparse
    # insertion order and dedupe, never a `set` (whose iteration order is not stable).
    ordered_ids: list[str] = []
    seen: set[str] = set()
    for cid in (*dense_norm, *sparse_norm):
        if cid not in seen:
            seen.add(cid)
            ordered_ids.append(cid)

    fused = [
        (cid, alpha * dense_norm.get(cid, 0.0) + (1 - alpha) * sparse_norm.get(cid, 0.0))
        for cid in ordered_ids
    ]
    # Stable sort: ties keep the deterministic dense-then-sparse insertion order above.
    ordered = sorted(fused, key=lambda kv: -kv[1])[:k]
    return [
        Candidate(chunk=chunk_by_id[cid], score=score, rank=rank)
        for rank, (cid, score) in enumerate(ordered)
    ]


class HybridRrfRetriever(Retriever):
    mode = "hybrid_rrf"

    def __init__(self):
        self._dense = DenseRetriever()
        self._sparse = Bm25Retriever()

    def retrieve(self, query: str, top_k: int, ctx: PipelineContext) -> list[Candidate]:
        rrf_k = getattr(ctx.config, "rrf_k", 60)
        dense = self._dense.retrieve(query, top_k, ctx)
        sparse = self._sparse.retrieve(query, top_k, ctx)
        return reciprocal_rank_fusion(dense, sparse, top_k, rrf_k)


class HybridWeightedRetriever(Retriever):
    mode = "hybrid_weighted"

    def __init__(self):
        self._dense = DenseRetriever()
        self._sparse = Bm25Retriever()

    def retrieve(self, query: str, top_k: int, ctx: PipelineContext) -> list[Candidate]:
        alpha = getattr(ctx.config, "alpha", 0.5)
        dense = self._dense.retrieve(query, top_k, ctx)
        sparse = self._sparse.retrieve(query, top_k, ctx)
        return weighted_fusion(dense, sparse, top_k, alpha)


# ---------------------------------------------------------------------------
# Multi-query merge (Req 16.4) — de-duplicates to the set-union of chunk ids
# ---------------------------------------------------------------------------

def merge_multi_query_candidates(per_query_results: list[list[Candidate]], top_k: int) -> list[Candidate]:
    """Merge candidate lists from N paraphrased queries, de-duplicating by chunk id.

    Keeps each chunk's best (highest) score across the paraphrase runs (Req 18 P18).
    """
    best: dict[str, Candidate] = {}
    for results in per_query_results:
        for cand in results:
            cid = cand.chunk.id
            if cid not in best or cand.score > best[cid].score:
                best[cid] = cand
    ordered = sorted(best.values(), key=lambda c: -c.score)[:top_k]
    return [Candidate(chunk=c.chunk, score=c.score, rank=i) for i, c in enumerate(ordered)]


def make_retriever(mode: str) -> Retriever:
    """Construct the Retriever registered under ``mode`` (Req 1.1, 4.1-4.4)."""
    if mode == "dense":
        return DenseRetriever()
    if mode == "bm25":
        return Bm25Retriever()
    if mode == "hybrid_rrf":
        return HybridRrfRetriever()
    if mode == "hybrid_weighted":
        return HybridWeightedRetriever()
    raise ValueError(f"Unknown retrieval option: '{mode}'")
